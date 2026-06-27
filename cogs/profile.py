import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from typing import Optional
import json
from pathlib import Path
from datetime import datetime
from .utils import (
    load_json, save_json, get_division_by_member, get_member_rank,
    get_member_join_date, count_division_members, DIVISIONS
)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PROFILES_FILE = DATA_DIR / "member_profiles.json"
DIVISION_PROFILES_FILE = DATA_DIR / "division_profiles.json"

class ProfileEditModal(Modal, title="Modifier votre profil"):
    color = TextInput(
        label="Couleur du profil (hex: #RRGGBB ou skip)",
        placeholder="#FF5733",
        max_length=7,
        required=False,
    )
    
    bio = TextInput(
        label="Biographie (max 100 caractères)",
        placeholder="À propos de toi...",
        max_length=100,
        required=False,
    )
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        profiles = load_json(PROFILES_FILE)
        user_key = str(interaction.user.id)
        
        if user_key not in profiles:
            profiles[user_key] = {
                "member_id": interaction.user.id,
                "member_name": interaction.user.name,
                "profile_color": "#2F3136",
                "bio": "",
                "profile_picture": None,
                "banner": None,
                "private": False,
                "created_at": datetime.now().isoformat(),
            }
        
        if self.color.value and self.color.value.startswith("#"):
            try:
                int(self.color.value[1:], 16)
                profiles[user_key]["profile_color"] = self.color.value
            except ValueError:
                pass
        
        if self.bio.value:
            profiles[user_key]["bio"] = self.bio.value
        
        save_json(PROFILES_FILE, profiles)
        
        await interaction.response.send_message("✅ Profil mise à jour!", ephemeral=True)

class ProfileManageView(View):
    def __init__(self, member_id: int):
        super().__init__(timeout=180)
        self.member_id = member_id

    @discord.ui.button(label="Changer couleur", style=discord.ButtonStyle.primary, emoji="🎨")
    async def color_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.member_id:
            await interaction.response.send_message("C'est pas ton profil!", ephemeral=True)
            return
        
        await interaction.response.send_modal(ProfileEditModal())

    @discord.ui.button(label="Changer PP", style=discord.ButtonStyle.primary, emoji="🖼️")
    async def pp_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.member_id:
            await interaction.response.send_message("C'est pas ton profil!", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "📤 Envoie une image pour ta PP (ou tape `none` pour supprimer)",
            ephemeral=True
        )

    @discord.ui.button(label="Changer bannière", style=discord.ButtonStyle.primary, emoji="🏳️")
    async def banner_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.member_id:
            await interaction.response.send_message("C'est pas ton profil!", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "📤 Envoie une image pour ta bannière (ou tape `none` pour supprimer)",
            ephemeral=True
        )

    @discord.ui.button(label="Profil privé", style=discord.ButtonStyle.secondary, emoji="🔐")
    async def private_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.member_id:
            await interaction.response.send_message("C'est pas ton profil!", ephemeral=True)
            return
        
        profiles = load_json(PROFILES_FILE)
        user_key = str(interaction.user.id)
        
        if user_key not in profiles:
            profiles[user_key] = {
                "member_id": interaction.user.id,
                "member_name": interaction.user.name,
                "profile_color": "#2F3136",
                "bio": "",
                "profile_picture": None,
                "banner": None,
                "private": False,
                "created_at": datetime.now().isoformat(),
            }
        
        profiles[user_key]["private"] = not profiles[user_key].get("private", False)
        save_json(PROFILES_FILE, profiles)
        
        status = "🔒 Privé" if profiles[user_key]["private"] else "🔓 Public"
        await interaction.response.send_message(f"✅ Profil maintenant {status}", ephemeral=True)

class ProfileManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="profil")
    async def profil(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        """Affiche le profil d'un membre."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        target = member or ctx.author
        
        profiles = load_json(PROFILES_FILE)
        target_key = str(target.id)
        
        if target_key not in profiles:
            profiles[target_key] = {
                "member_id": target.id,
                "member_name": target.name,
                "profile_color": "#2F3136",
                "bio": "",
                "profile_picture": None,
                "banner": None,
                "private": False,
                "created_at": datetime.now().isoformat(),
            }
            save_json(PROFILES_FILE, profiles)
        
        profile = profiles[target_key]
        
        if profile.get("private") and target.id != ctx.author.id:
            await ctx.reply("🔒 Ce profil est privé.")
            return
        
        member_division = get_division_by_member(target)
        division_name = member_division[0] if member_division else "Aucune"
        rank = None
        join_date = None
        
        if member_division:
            rank = get_member_rank(target.id, division_name)
            join_date = get_member_join_date(target.id, division_name)
        
        try:
            color = discord.Color(int(profile.get("profile_color", "#2F3136")[1:], 16))
        except:
            color = discord.Color.greyple()
        
        embed = discord.Embed(
            title=f"{target.name}",
            description=profile.get("bio", "Aucune biographie"),
            color=color,
        )
        
        embed.set_thumbnail(url=profile.get("profile_picture") or target.display_avatar.url)
        if profile.get("banner"):
            embed.set_image(url=profile.get("banner"))
        
        embed.add_field(name="Division", value=division_name, inline=True)
        
        if rank:
            embed.add_field(name="Rang", value=rank, inline=True)
        
        if join_date:
            try:
                join_dt = datetime.fromisoformat(join_date)
                days = (datetime.now() - join_dt).days
                embed.add_field(name="Membre depuis", value=f"{days} jours", inline=True)
            except:
                pass
        
        embed.set_footer(text=f"Profil de {target.name}")
        
        view = None
        if target.id == ctx.author.id:
            view = ProfileManageView(target.id)
        
        await ctx.send(embed=embed, view=view)

    @commands.command(name="divinfo")
    async def divinfo(self, ctx: commands.Context, division_num: str) -> None:
        """Affiche les infos d'une division."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        division_name = f"Division {division_num}"
        
        if division_name not in DIVISIONS:
            await ctx.reply("❌ Division introuvable.", delete_after=5)
            return
        
        division_data = DIVISIONS[division_name]
        role = ctx.guild.get_role(division_data["role_id"])
        
        if not role:
            await ctx.reply("❌ Impossible de charger la division.", delete_after=5)
            return
        
        division_profiles = load_json(DIVISION_PROFILES_FILE)
        div_key = division_name
        
        if div_key not in division_profiles:
            division_profiles[div_key] = {
                "name": division_name,
                "description": "Aucune description",
                "color": "#2F3136",
                "banner": None,
                "private": False,
                "created_at": datetime.now().isoformat(),
            }
            save_json(DIVISION_PROFILES_FILE, division_profiles)
        
        div_profile = division_profiles[div_key]
        
        if div_profile.get("private"):
            captain_role = ctx.guild.get_role(1520199922752819381)
            if not (captain_role and captain_role in ctx.author.roles):
                await ctx.reply("🔒 Les infos de cette division sont privées.")
                return
        
        try:
            color = discord.Color(int(div_profile.get("color", "#2F3136")[1:], 16))
        except:
            color = discord.Color.greyple()
        
        embed = discord.Embed(
            title=division_name,
            description=div_profile.get("description", "Aucune description"),
            color=color,
        )
        
        if div_profile.get("banner"):
            embed.set_image(url=div_profile.get("banner"))
        
        member_count = len(role.members)
        embed.add_field(name="Membres", value=f"{member_count}/8", inline=True)
        embed.add_field(name="Rôle", value=role.mention, inline=True)
        
        members_list = "\n".join([f"• {m.mention} ({m.name})" for m in role.members[:10]])
        if len(role.members) > 10:
            members_list += f"\n... et {len(role.members) - 10} de plus"
        
        embed.add_field(name="Membres de la division", value=members_list or "Aucun membre", inline=False)
        
        embed.set_footer(text=f"Division créée: {div_profile.get('created_at', 'Inconnu')}")
        
        await ctx.send(embed=embed)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(ProfileManager(bot))
