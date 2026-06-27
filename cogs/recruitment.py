import os
import discord
from discord.ext import commands
from discord.ui import View, Select, Button, select
from typing import Optional, Dict, List
import json
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
from .utils import (
    load_json, save_json, get_division_by_member, count_division_members,
    is_member_banned, ban_member, unban_member, can_rejoin_after_kick,
    set_kick_cooldown, can_rejoin_after_leave, set_leave_cooldown,
    add_member_to_division, get_member_divisions, DIVISIONS,
    LIEUTENANT_ROLE_ID, VICE_CAPTAIN_ROLE_ID, DIVISION_CAPTAIN_ROLE_ID
)

DATA_DIR = Path(os.getenv("DATA_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", str(Path(__file__).parent.parent / "data"))))
DATA_DIR.mkdir(parents=True, exist_ok=True)
APPLICATIONS_FILE = DATA_DIR / "applications.json"

# Configuration des divisions avec channels supplémentaires
DIVISION_CHANNELS = {
    "Division 1": {"entrants": 1520183224561827870, "category": 1520182538852130926},
    "Division 6": {"entrants": 1520185587926302730, "category": 1520185456181829663},
    "Division 10": {"entrants": 1520199186916573335, "category": 1520193979872559267},
    "Division 11": {"entrants": 1520213126799425747, "category": 1520212998555889664},
}

# member division helpers are in utils.py (imported above)

class ApplicationTicketView(View):
    """View dynamique et persistante pour un ticket d'application.
    Les boutons utilisent des custom_id contenant la clé d'application pour restaurer la view après reboot.
    """
    def __init__(self, app_key: str, member_id: int, division_name: str, captain_id: int, vice_id: Optional[int], ticket_channel_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.app_key = app_key
        self.member_id = member_id
        self.division_name = division_name
        self.captain_id = captain_id
        self.vice_id = vice_id
        self.ticket_channel_id = ticket_channel_id

        # boutons persistants (custom_id inclut la clé d'application)
        self.accept_btn = Button(label="Accepter", style=discord.ButtonStyle.success, emoji="✅", custom_id=f"app_accept_{self.app_key}")
        self.refuse_btn = Button(label="Refuser", style=discord.ButtonStyle.danger, emoji="❌", custom_id=f"app_refuse_{self.app_key}")
        self.close_btn = Button(label="Fermer", style=discord.ButtonStyle.secondary, emoji="🔐", custom_id=f"app_close_{self.app_key}")

        # Assign callbacks
        self.accept_btn.callback = self._accept_callback
        self.refuse_btn.callback = self._refuse_callback
        self.close_btn.callback = self._close_callback

        self.add_item(self.accept_btn)
        self.add_item(self.refuse_btn)
        self.add_item(self.close_btn)

    async def _load_application(self) -> dict:
        apps = load_json(APPLICATIONS_FILE)
        return apps.get(self.app_key, {})

    async def _save_application(self, data: dict) -> None:
        apps = load_json(APPLICATIONS_FILE)
        apps[self.app_key] = data
        save_json(APPLICATIONS_FILE, apps)

    async def _accept_callback(self, interaction: discord.Interaction) -> None:
        app = await self._load_application()
        member = interaction.guild.get_member(app.get("member_id")) if interaction.guild else None
        is_captain = interaction.user.id == self.captain_id
        is_vice = self.vice_id and interaction.user.id == self.vice_id

        if not (is_captain or is_vice):
            await interaction.response.send_message("Seul le capitaine ou le vice-capitaine peut accepter.", ephemeral=True)
            return

        await interaction.response.defer()

        if is_vice and not is_captain:
            embed = discord.Embed(title="✅ Recommendation du Vice-Capitaine", description=f"<@{self.vice_id}> recommande l'acceptation de <@{self.member_id}>.", color=discord.Color.blue())
            embed.add_field(name="Division", value=self.division_name, inline=False)
            embed.add_field(name="Candidat", value=f"<@{self.member_id}>", inline=False)
            channel = interaction.guild.get_channel(self.ticket_channel_id) if interaction.guild else None
            if channel:
                await channel.send(embed=embed)
            try:
                await interaction.client.get_user(self.captain_id).send(f"<@{self.vice_id}> a validé la candidature de <@{self.member_id}> pour {self.division_name}.")
            except discord.Forbidden:
                pass

            # persist
            app.setdefault("messages", []).append({"timestamp": datetime.now().isoformat(), "author_id": self.vice_id, "content": "Recommendation accept"})
            app["status"] = app.get("status", "pending")
            await self._save_application(app)
            return

        # Captain finalise l'acceptation
        division_data = DIVISIONS.get(self.division_name)
        if not division_data:
            await interaction.followup.send("Division introuvable.", ephemeral=True)
            return

        role = interaction.guild.get_role(division_data["role_id"]) if interaction.guild else None
        if not role:
            await interaction.followup.send("Rôle de division introuvable.", ephemeral=True)
            return

        try:
            if member:
                await member.add_roles(role, reason=f"Candidature acceptée - {self.division_name}")
            add_member_to_division(self.member_id, self.division_name)

            channel = interaction.guild.get_channel(self.ticket_channel_id) if interaction.guild else None
            if channel:
                await channel.send(embed=discord.Embed(title="✅ Candidature acceptée", description=f"<@{self.member_id}> a été accepté(e) dans **{self.division_name}**!", color=discord.Color.green()))
            try:
                await interaction.client.get_user(self.member_id).send(f"✅ Votre candidature pour **{self.division_name}** a été acceptée!")
            except discord.Forbidden:
                pass

            app["status"] = "accepted"
            app.setdefault("messages", []).append({"timestamp": datetime.now().isoformat(), "author_id": interaction.user.id, "content": "Candidature acceptée"})
            await self._save_application(app)

            # disable buttons on original message
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

            # delete channel after short delay and send transcript
            await asyncio.sleep(5)
            if channel:
                # send transcript
                await self._send_transcript_and_delete(channel, interaction.client.get_user(self.member_id))
        except discord.Forbidden:
            await interaction.followup.send("Impossible d'ajouter le rôle au membre.", ephemeral=True)

    async def _refuse_callback(self, interaction: discord.Interaction) -> None:
        app = await self._load_application()
        is_captain = interaction.user.id == self.captain_id
        is_vice = self.vice_id and interaction.user.id == self.vice_id

        if not (is_captain or is_vice):
            await interaction.response.send_message("Seul le capitaine ou le vice-capitaine peut refuser.", ephemeral=True)
            return

        await interaction.response.defer()

        channel = interaction.guild.get_channel(self.ticket_channel_id) if interaction.guild else None
        if is_vice and not is_captain:
            embed = discord.Embed(title="❌ Recommendation negative du Vice-Capitaine", description=f"<@{self.vice_id}> ne recommande pas l'acceptation de <@{self.member_id}>.", color=discord.Color.orange())
            embed.add_field(name="Division", value=self.division_name, inline=False)
            embed.add_field(name="Candidat", value=f"<@{self.member_id}>", inline=False)
            if channel:
                await channel.send(embed=embed)
            try:
                await interaction.client.get_user(self.captain_id).send(f"<@{self.vice_id}> recommande le refus de <@{self.member_id}> pour {self.division_name}.")
            except discord.Forbidden:
                pass

            app.setdefault("messages", []).append({"timestamp": datetime.now().isoformat(), "author_id": self.vice_id, "content": "Recommendation refuse"})
            await self._save_application(app)
            return

        # Captain refuses
        if channel:
            await channel.send(embed=discord.Embed(title="❌ Candidature refusée", description=f"La candidature pour **{self.division_name}** a été refusée.", color=discord.Color.red()))
        try:
            await interaction.client.get_user(self.member_id).send(f"❌ Votre candidature pour **{self.division_name}** a été refusée.")
        except discord.Forbidden:
            pass

        app["status"] = "refused"
        app.setdefault("messages", []).append({"timestamp": datetime.now().isoformat(), "author_id": interaction.user.id, "content": "Candidature refuse"})
        await self._save_application(app)

        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        await asyncio.sleep(5)
        if channel:
            await self._send_transcript_and_delete(channel, interaction.client.get_user(self.member_id))

    async def _close_callback(self, interaction: discord.Interaction) -> None:
        app = await self._load_application()
        is_captain = interaction.user.id == self.captain_id
        is_member = interaction.user.id == self.member_id

        if not (is_captain or is_member):
            await interaction.response.send_message("Seul le capitaine ou le candidat peut fermer le ticket.", ephemeral=True)
            return

        await interaction.response.defer()

        channel = interaction.guild.get_channel(self.ticket_channel_id) if interaction.guild else None
        if channel:
            await channel.send(embed=discord.Embed(title="🔐 Ticket fermé", description=f"Ce ticket a été fermé par {interaction.user.mention}.", color=discord.Color.greyple()))

        app.setdefault("messages", []).append({"timestamp": datetime.now().isoformat(), "author_id": interaction.user.id, "content": "Ticket ferme"})
        await self._save_application(app)
        await self._send_transcript_and_delete(channel, interaction.client.get_user(self.member_id))

    async def _send_transcript_and_delete(self, channel: discord.TextChannel, member_user: Optional[discord.User]) -> None:
        # Build transcript from stored messages
        apps = load_json(APPLICATIONS_FILE)
        app = apps.get(self.app_key, {})
        transcript = f"=== Ticket de candidature ===\n"
        transcript += f"Candidat: <@{self.member_id}>\n"
        transcript += f"Division: {self.division_name}\n"
        transcript += f"Date: {app.get('created_at', 'Unknown')}\n"
        transcript += f"Statut: {app.get('status', 'Unknown')}\n\n--- Messages ---\n"
        for msg in app.get('messages', []):
            transcript += f"[{msg.get('timestamp')}] <{msg.get('author_id')}>: {msg.get('content')}\n"

        file = discord.File(fp=__import__('io').BytesIO(transcript.encode()), filename=f"ticket_{self.member_id}_{self.division_name}.txt")
        try:
            if member_user:
                await member_user.send(file=file)
        except discord.Forbidden:
            pass
        try:
            # send to captain via guild member if possible
            if channel and channel.guild:
                captain_member = channel.guild.get_member(self.captain_id)
                if captain_member:
                    try:
                        await captain_member.send(file=file)
                    except discord.Forbidden:
                        pass
        except Exception:
            pass

        # delete channel
        try:
            await channel.delete(reason="Ticket terminé")
        except Exception:
            pass

class RecruitmentSelectView(View):
    def __init__(self, member: discord.Member, bot: commands.Bot):
        super().__init__(timeout=180)
        self.member = member
        self.bot = bot
        self.add_item(self.division_select())
    
    @select(
        placeholder="Choisis la division où tu veux postuler",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Division 1", value="Division 1"),
            discord.SelectOption(label="Division 6", value="Division 6"),
            discord.SelectOption(label="Division 10", value="Division 10"),
            discord.SelectOption(label="Division 11", value="Division 11"),
        ]
    )
    async def division_select(self, interaction: discord.Interaction, select: Select) -> None:
        division_name = select.values[0]
        
        if is_member_banned(self.member.id):
            await interaction.response.send_message("❌ Tu es banni(e) et ne peux pas postuler.", ephemeral=True)
            return
        
        if not can_rejoin_after_kick(self.member.id, division_name):
            await interaction.response.send_message("⏳ Tu dois attendre 3 jours avant de pouvoir repostuler après une expulsion.", ephemeral=True)
            return
        
        if not can_rejoin_after_leave(self.member.id):
            await interaction.response.send_message("⏳ Tu dois attendre 3 jours avant de pouvoir repostuler après avoir quitté une division.", ephemeral=True)
            return
        
        member_count = count_division_members(interaction.guild, division_name)
        if member_count >= 8:
            await interaction.response.send_message("❌ Cette division est pleine!", ephemeral=True)
            return
        
        if get_division_by_member(self.member):
            await interaction.response.send_message("❌ Tu dois quitter ta division actuelle avant de postuler à une autre.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        division_data = DIVISIONS.get(division_name)
        if not division_data:
            await interaction.followup.send("Division introuvable.", ephemeral=True)
            return
        
        guild = interaction.guild
        category = guild.get_channel(division_data["channels"]["category"]) if "category" in division_data["channels"] else None
        entrants_channel = guild.get_channel(division_data["channels"]["entrants"])
        
        if not entrants_channel:
            await interaction.followup.send("Canal des entrants introuvable.", ephemeral=True)
            return
        
        captain_role = guild.get_role(DIVISION_CAPTAIN_ROLE_ID)
        vice_captain_role = guild.get_role(VICE_CAPTAIN_ROLE_ID)
        
        captains = [m for m in guild.members if captain_role in m.roles]
        vice_captains = [m for m in guild.members if vice_captain_role in m.roles]
        
        captain = captains[0] if captains else None
        vice_captain = vice_captains[0] if vice_captains else None
        
        if not captain:
            await interaction.followup.send("Aucun capitaine trouvé pour cette division.", ephemeral=True)
            return
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view=False),
            guild.me: discord.PermissionOverwrite(view=True, manage_channels=True, manage_messages=True),
            self.member: discord.PermissionOverwrite(view=True, send_messages=True, read_message_history=True),
            captain: discord.PermissionOverwrite(view=True, send_messages=True, read_message_history=True, manage_messages=True),
        }
        
        if vice_captain:
            overwrites[vice_captain] = discord.PermissionOverwrite(view=True, send_messages=True, read_message_history=True)
        
        channel_name = f"candidature-{self.member.name.lower()}"
        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket de candidature pour {self.member.name} - {division_name}"
        )
        
        # prepare persistent application entry
        created_at = datetime.now().isoformat()
        app_key = f"{self.member.id}_{division_name}_{created_at}"
        application_entry = {
            "app_key": app_key,
            "member_id": self.member.id,
            "division": division_name,
            "status": "pending",
            "messages": [],
            "created_at": created_at,
            "channel_id": ticket_channel.id,
            "message_id": None,
            "captain_id": captain.id if captain else None,
            "vice_id": vice_captain.id if vice_captain else None,
        }
        apps = load_json(APPLICATIONS_FILE)
        apps[app_key] = application_entry
        save_json(APPLICATIONS_FILE, apps)

        # create view using app_key and register after sending message
        view = ApplicationTicketView(app_key, self.member.id, division_name, captain.id if captain else None, vice_captain.id if vice_captain else None, ticket_channel.id)

        embed = discord.Embed(
            title=f"📋 Candidature - {division_name}",
            description=f"Bienvenue {self.member.mention}! Votre candidature est en cours d'examen.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Division", value=division_name, inline=False)
        embed.add_field(name="Candidat", value=self.member.mention, inline=False)
        embed.set_thumbnail(url=self.member.display_avatar.url)
        
        welcome_msg = await ticket_channel.send(embed=embed, view=view)
        # save message id for persistence
        apps = load_json(APPLICATIONS_FILE)
        if app_key in apps:
            apps[app_key]["message_id"] = welcome_msg.id
            save_json(APPLICATIONS_FILE, apps)

        await welcome_msg.pin(reason="Message de bienvenue du ticket")
        
        pin_notification = await ticket_channel.fetch_message(ticket_channel.last_message_id)
        try:
            await pin_notification.delete()
        except:
            pass
        
        await self.member.send(f"✅ Votre candidature pour **{division_name}** a été créée! Un ticket privé a été ouvert.")
        await interaction.followup.send("✅ Candidature créée avec succès!", ephemeral=True)

        # register persistent view so buttons keep working after restarts
        try:
            if hasattr(self.bot, 'add_view'):
                self.bot.add_view(view, message_id=welcome_msg.id)
        except Exception:
            pass

class RecruitmentManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Restore persistent application views so buttons keep working after restarts
        try:
            apps = load_json(APPLICATIONS_FILE)
            for app_key, app in apps.items():
                message_id = app.get("message_id")
                channel_id = app.get("channel_id")
                if message_id:
                    view = ApplicationTicketView(app_key, app.get("member_id"), app.get("division"), app.get("captain_id"), app.get("vice_id"), channel_id)
                    try:
                        bot.add_view(view, message_id=message_id)
                    except Exception:
                        pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Persist messages sent inside ticket channels to APPLICATIONS_FILE
        if message.author.bot:
            return
        apps = load_json(APPLICATIONS_FILE)
        updated = False
        for app_key, app in apps.items():
            if app.get("channel_id") == getattr(message.channel, 'id', None):
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "author_id": message.author.id,
                    "content": message.content,
                    "attachments": [a.url for a in message.attachments] if message.attachments else [],
                }
                app.setdefault("messages", []).append(entry)
                apps[app_key] = app
                updated = True
                break
        if updated:
            save_json(APPLICATIONS_FILE, apps)

    @commands.command(name="postuler")
    async def postuler(self, ctx: commands.Context) -> None:
        """Ouvre le menu pour postuler à une division."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        embed = discord.Embed(
            title="📋 Système de Candidature",
            description="Clique sur le bouton ci-dessous pour candidater à une division.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        view = RecruitmentSelectView(ctx.author, self.bot)
        await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecruitmentManager(bot))

