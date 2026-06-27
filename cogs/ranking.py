import discord
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional
import json
from pathlib import Path
from datetime import datetime, timedelta
from .utils import (
    load_json, save_json, get_division_by_member, get_member_rank,
    set_member_rank, can_rank, set_rank_cooldown, get_rank_holder,
    is_member_banned, unban_member, can_rejoin_after_kick, set_kick_cooldown,
    can_rejoin_after_leave, set_leave_cooldown, get_member_divisions, add_member_to_division,
    DIVISIONS, LIEUTENANT_ROLE_ID, VICE_CAPTAIN_ROLE_ID, DIVISION_CAPTAIN_ROLE_ID
)

class ConfirmView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.confirmed = False

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Seul le capitaine peut confirmer.", ephemeral=True)
            return
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Seul le capitaine peut annuler.", ephemeral=True)
            return
        await interaction.response.defer()
        self.stop()

class RankingManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="rank")
    async def rank(self, ctx: commands.Context, member: discord.Member, rank_type: int) -> None:
        """Promote un membre: 1 pour Lieutenant, 2 pour Vice-Capitaine."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        captain_role = ctx.guild.get_role(DIVISION_CAPTAIN_ROLE_ID)
        if not captain_role or captain_role not in ctx.author.roles:
            await ctx.reply("❌ Seul un capitaine peut utiliser cette commande.", delete_after=5)
            return
        
        captain_division = get_division_by_member(ctx.author)
        if not captain_division:
            await ctx.reply("❌ Impossible de déterminer ta division.", delete_after=5)
            return
        
        division_name, _ = captain_division
        member_division = get_division_by_member(member)
        if not member_division or member_division[0] != division_name:
            await ctx.reply(f"❌ Ce membre n'est pas dans ta division.", delete_after=5)
            return
        
        if rank_type not in [1, 2]:
            await ctx.reply("❌ Rang invalide. 1 pour Lieutenant, 2 pour Vice-Capitaine.", delete_after=5)
            return
        
        rank_name = "Lieutenant" if rank_type == 1 else "Vice-Capitaine"
        rank_role_id = LIEUTENANT_ROLE_ID if rank_type == 1 else VICE_CAPTAIN_ROLE_ID
        
        if not can_rank(ctx.author.id, division_name, rank_type):
            await ctx.reply(f"⏳ Tu dois attendre 10 jours avant de changer de {rank_name}.", delete_after=5)
            return
        
        existing_holder = get_rank_holder(ctx.guild, division_name, rank_type)
        if existing_holder and existing_holder.id != member.id:
            await ctx.reply(f"❌ Un {rank_name} est déjà nommé. Utilise `d!unrank @{existing_holder.name}` d'abord.", delete_after=5)
            return
        
        embed = discord.Embed(
            title=f"Confirmation - Promotion en {rank_name}",
            description=f"Tu vas promouvoir {member.mention} en **{rank_name}** pour **{division_name}**.\n\nCette action ne peut être refaite que dans 10 jours.",
            color=discord.Color.blue(),
        )
        
        view = ConfirmView(ctx.author.id)
        msg = await ctx.reply(embed=embed, view=view)
        
        await view.wait()
        
        if not view.confirmed:
            await msg.edit(content="❌ Action annulée.", embed=None, view=None)
            return
        
        try:
            rank_role = ctx.guild.get_role(rank_role_id)
            if rank_role:
                await member.add_roles(rank_role, reason=f"Promotion en {rank_name} - {division_name}")
            
            set_member_rank(member.id, division_name, rank_name)
            set_rank_cooldown(ctx.author.id, division_name, rank_type)
            
            embed = discord.Embed(
                title=f"✅ {rank_name} nommé(e)",
                description=f"{member.mention} est maintenant **{rank_name}** de **{division_name}**!",
                color=discord.Color.green(),
            )
            await msg.edit(embed=embed, view=None)
            
            await member.send(f"🎉 Félicitations! Tu as été promu(e) en **{rank_name}** pour **{division_name}**!")
        except discord.Forbidden:
            await msg.edit(content="❌ Je n'ai pas les permissions nécessaires.", embed=None, view=None)

    @commands.command(name="unrank")
    async def unrank(self, ctx: commands.Context, member: discord.Member) -> None:
        """Retire le rang d'un membre."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        captain_role = ctx.guild.get_role(DIVISION_CAPTAIN_ROLE_ID)
        if not captain_role or captain_role not in ctx.author.roles:
            await ctx.reply("❌ Seul un capitaine peut utiliser cette commande.", delete_after=5)
            return
        
        member_division = get_division_by_member(member)
        if not member_division:
            await ctx.reply("❌ Ce membre n'a aucun rang.", delete_after=5)
            return
        
        division_name, _ = member_division
        rank = get_member_rank(member.id, division_name)
        
        if not rank:
            await ctx.reply("❌ Ce membre n'a aucun rang.", delete_after=5)
            return
        
        try:
            for role_id in [LIEUTENANT_ROLE_ID, VICE_CAPTAIN_ROLE_ID]:
                role = ctx.guild.get_role(role_id)
                if role and role in member.roles:
                    await member.remove_roles(role, reason=f"Derank")
            
            set_member_rank(member.id, division_name, None)
            
            await ctx.reply(f"✅ {member.mention} a perdu son rang de **{rank}**.", delete_after=5)
            await member.send(f"⚠️ Tu as perdu ton rang de **{rank}** dans **{division_name}**.")
        except discord.Forbidden:
            await ctx.reply("❌ Je n'ai pas les permissions nécessaires.", delete_after=5)

    @commands.command(name="kick")
    async def kick(self, ctx: commands.Context, member: discord.Member) -> None:
        """Expulse un membre d'une division."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        captain_role = ctx.guild.get_role(DIVISION_CAPTAIN_ROLE_ID)
        if not captain_role or captain_role not in ctx.author.roles:
            await ctx.reply("❌ Seul un capitaine peut utiliser cette commande.", delete_after=5)
            return
        
        captain_division = get_division_by_member(ctx.author)
        if not captain_division:
            await ctx.reply("❌ Impossible de déterminer ta division.", delete_after=5)
            return
        
        member_division = get_division_by_member(member)
        if not member_division or member_division[0] != captain_division[0]:
            await ctx.reply("❌ Ce membre n'est pas dans ta division.", delete_after=5)
            return
        
        division_name = captain_division[0]
        
        embed = discord.Embed(
            title="Confirmation - Expulsion",
            description=f"Tu vas expulser {member.mention} de **{division_name}**.\n\nIl ne pourra repostuler que dans 3 jours.",
            color=discord.Color.orange(),
        )
        
        view = ConfirmView(ctx.author.id)
        msg = await ctx.reply(embed=embed, view=view)
        
        await view.wait()
        
        if not view.confirmed:
            await msg.edit(content="❌ Action annulée.", embed=None, view=None)
            return
        
        try:
            division_data = DIVISIONS.get(division_name)
            role = ctx.guild.get_role(division_data["role_id"]) if division_data else None
            
            if role:
                await member.remove_roles(role, reason="Expulsion")
            
            for role_id in [LIEUTENANT_ROLE_ID, VICE_CAPTAIN_ROLE_ID]:
                role = ctx.guild.get_role(role_id)
                if role and role in member.roles:
                    await member.remove_roles(role)
            
            if member.nick and member.nick.startswith(f"[{division_name}]"):
                await member.edit(nick=None, reason="Expulsion")
            
            set_kick_cooldown(member.id, division_name)
            
            embed = discord.Embed(
                title="✅ Membre expulsé",
                description=f"{member.mention} a été expulsé de **{division_name}**.",
                color=discord.Color.green(),
            )
            await msg.edit(embed=embed, view=None)
            
            await member.send(f"⚠️ Tu as été expulsé(e) de **{division_name}**.\nTu peux repostuler dans 3 jours.")
        except discord.Forbidden:
            await msg.edit(content="❌ Je n'ai pas les permissions nécessaires.", embed=None, view=None)

    @commands.command(name="ban")
    async def ban(self, ctx: commands.Context, member: discord.Member) -> None:
        """Bannit définitivement un membre."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        captain_role = ctx.guild.get_role(DIVISION_CAPTAIN_ROLE_ID)
        if not captain_role or captain_role not in ctx.author.roles:
            await ctx.reply("❌ Seul un capitaine peut utiliser cette commande.", delete_after=5)
            return
        
        embed = discord.Embed(
            title="Confirmation - Ban",
            description=f"Tu vas bannir **{member.mention}** de toutes les divisions.\n\nIl ne pourra plus postuler jusqu'au débannissement.",
            color=discord.Color.red(),
        )
        
        view = ConfirmView(ctx.author.id)
        msg = await ctx.reply(embed=embed, view=view)
        
        await view.wait()
        
        if not view.confirmed:
            await msg.edit(content="❌ Action annulée.", embed=None, view=None)
            return
        
        try:
            ban_member(member.id)
            member_divisions = get_member_divisions(member.id)
            
            for div_name in member_divisions:
                division_data = DIVISIONS.get(div_name)
                if division_data:
                    role = ctx.guild.get_role(division_data["role_id"])
                    if role and role in member.roles:
                        await member.remove_roles(role)
            
            embed = discord.Embed(
                title="✅ Membre banni",
                description=f"{member.mention} a été banni de toutes les divisions.",
                color=discord.Color.green(),
            )
            await msg.edit(embed=embed, view=None)
            
            await member.send("🚫 Tu as été banni(e) et ne peux plus postuler à aucune division.")
        except discord.Forbidden:
            await msg.edit(content="❌ Je n'ai pas les permissions nécessaires.", embed=None, view=None)

    @commands.command(name="deban")
    async def deban(self, ctx: commands.Context, member: discord.Member) -> None:
        """Débannit un membre."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        captain_role = ctx.guild.get_role(DIVISION_CAPTAIN_ROLE_ID)
        if not captain_role or captain_role not in ctx.author.roles:
            await ctx.reply("❌ Seul un capitaine peut utiliser cette commande.", delete_after=5)
            return
        
        if not is_member_banned(member.id):
            await ctx.reply("❌ Ce membre n'est pas banni.", delete_after=5)
            return
        
        unban_member(member.id)
        
        await ctx.reply(f"✅ {member.mention} a été débanni.", delete_after=5)
        await member.send("✅ Tu as été débanni et peux à nouveau postuler!")

    @commands.command(name="quitter")
    async def quitter(self, ctx: commands.Context) -> None:
        """Quitte ta division actuelle."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        
        member_division = get_division_by_member(ctx.author)
        if not member_division:
            await ctx.reply("❌ Tu n'es dans aucune division.", delete_after=5)
            return
        
        division_name, division_data = member_division
        
        embed = discord.Embed(
            title="Confirmation - Quitter",
            description=f"Tu vas quitter **{division_name}**.\n\nTu ne pourras repostuler que dans 3 jours.",
            color=discord.Color.orange(),
        )
        
        view = ConfirmView(ctx.author.id)
        msg = await ctx.reply(embed=embed, view=view)
        
        await view.wait()
        
        if not view.confirmed:
            await msg.edit(content="❌ Action annulée.", embed=None, view=None)
            return
        
        try:
            role = ctx.guild.get_role(division_data["role_id"])
            if role:
                await ctx.author.remove_roles(role, reason="Départ volontaire")
            
            for role_id in [LIEUTENANT_ROLE_ID, VICE_CAPTAIN_ROLE_ID]:
                role = ctx.guild.get_role(role_id)
                if role and role in ctx.author.roles:
                    await ctx.author.remove_roles(role)
            
            if ctx.author.nick and ctx.author.nick.startswith(f"[{division_name}]"):
                await ctx.author.edit(nick=None, reason="Départ de la division")
            
            set_leave_cooldown(ctx.author.id)
            
            embed = discord.Embed(
                title="✅ Division quittée",
                description=f"Tu as quitté **{division_name}**.\n⏳ Tu pourras repostuler dans 3 jours.",
                color=discord.Color.green(),
            )
            await msg.edit(embed=embed, view=None)
        except discord.Forbidden:
            await msg.edit(content="❌ Je n'ai pas les permissions nécessaires.", embed=None, view=None)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RankingManager(bot))
