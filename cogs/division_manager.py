import os
import discord
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional
import json
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(os.getenv("DATA_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", str(Path(__file__).parent.parent / "data"))))
DATA_DIR.mkdir(parents=True, exist_ok=True)
BLOCKS_FILE = DATA_DIR / "blocks.json"
CONFIGS_FILE = DATA_DIR / "divisions_config.json"
COOLDOWNS_FILE = DATA_DIR / "cooldowns.json"

DIVISIONS = {
    "Division 1": {
        "role_id": 1520173789957062787,
        "channels": {
            "main": 1520182625807892550,
            "annonces": 1520182625807892550,
            "entrants": 1520183224561827870,
            "sortants": 1520183267230351370,
        },
    },
    "Division 6": {
        "role_id": 1520180291061415957,
        "channels": {
            "main": 1520185465817272391,
            "annonces": 1520185555516915913,
            "entrants": 1520185587926302730,
            "sortants": 1520185614081851453,
        },
    },
    "Division 10": {
        "role_id": 1520199862216425534,
        "channels": {
            "main": 1520194245997363341,
            "annonces": 1520199186916573335,
            "entrants": 1520199186916573335,
            "sortants": 1520199247822065854,
        },
    },
    "Division 11": {
        "role_id": 1520199922752819381,
        "channels": {
            "main": 1520199431532576788,
            "annonces": 1520213097376256081,
            "entrants": 1520213126799425747,
            "sortants": 1520213148865663017,
        },
    },
}

DIVISION_CAPTAIN_ROLE_ID = 1520199922752819381

def load_json(filepath: Path) -> dict:
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filepath: Path, data: dict) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_division_by_member(member: discord.Member) -> Optional[tuple[str, dict]]:
    for name, data in DIVISIONS.items():
        if member.get_role(data["role_id"]):
            return name, data
    return None

def get_division_number(division_name: str) -> str:
    return division_name.split()[-1]

def format_division_prefix(division_name: str) -> str:
    return division_name.replace("Division", "Div").strip()

def build_nickname(member: discord.Member, division_name: str) -> str:
    prefix = f"[{format_division_prefix(division_name)}] "
    base_name = member.nick or member.name
    if base_name.startswith(prefix):
        return base_name
    new_nick = prefix + base_name
    if len(new_nick) <= 32:
        return new_nick
    truncated = base_name[: 32 - len(prefix)]
    return prefix + truncated

def is_member_blocked(member_id: int, division_name: str) -> bool:
    blocks = load_json(BLOCKS_FILE)
    member_key = str(member_id)
    return division_name in blocks.get(member_key, [])

def block_member_from_division(member_id: int, division_name: str) -> None:
    blocks = load_json(BLOCKS_FILE)
    member_key = str(member_id)
    if member_key not in blocks:
        blocks[member_key] = []
    if division_name not in blocks[member_key]:
        blocks[member_key].append(division_name)
    save_json(BLOCKS_FILE, blocks)

def unblock_member_from_division(member_id: int, division_name: str) -> None:
    blocks = load_json(BLOCKS_FILE)
    member_key = str(member_id)
    if member_key in blocks and division_name in blocks[member_key]:
        blocks[member_key].remove(division_name)
        if not blocks[member_key]:
            del blocks[member_key]
    save_json(BLOCKS_FILE, blocks)

def get_blocked_divisions(member_id: int) -> list[str]:
    blocks = load_json(BLOCKS_FILE)
    return blocks.get(str(member_id), [])

def load_division_config(division_name: str) -> dict:
    configs = load_json(CONFIGS_FILE)
    return configs.get(division_name, {})

def save_division_config(division_name: str, config: dict) -> None:
    configs = load_json(CONFIGS_FILE)
    configs[division_name] = config
    save_json(CONFIGS_FILE, configs)

def check_cooldown(captain_id: int, division_name: str, cooldown_days: int) -> Optional[datetime]:
    cooldowns = load_json(COOLDOWNS_FILE)
    key = f"{captain_id}_{division_name}"
    last_update = cooldowns.get(key)
    if not last_update:
        return None
    
    last_time = datetime.fromisoformat(last_update)
    next_allowed = last_time + timedelta(days=cooldown_days)
    if datetime.now() < next_allowed:
        return next_allowed
    return None

def set_cooldown(captain_id: int, division_name: str) -> None:
    cooldowns = load_json(COOLDOWNS_FILE)
    key = f"{captain_id}_{division_name}"
    cooldowns[key] = datetime.now().isoformat()
    save_json(COOLDOWNS_FILE, cooldowns)

def is_division_captain():
    def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")
        return bool(ctx.author.get_role(DIVISION_CAPTAIN_ROLE_ID))
    return commands.check(predicate)


class InvitationView(View):
    def __init__(
        self,
        manager: "DivisionManager",
        member: discord.Member,
        division_name: str,
        division_role_id: int,
        captain_id: int,
    ) -> None:
        super().__init__(timeout=180.0)
        self.manager = manager
        self.member = member
        self.division_name = division_name
        self.division_role_id = division_role_id
        self.captain_id = captain_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "Seul le membre invité peut répondre à cette invitation.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        self.manager.end_invitation(self.captain_id)
        if not self.message or not self.message.embeds:
            return

        embed = self.message.embeds[0]
        embed.title = "Invitation expirée"
        embed.description = (
            f"{self.member.mention}, l'invitation à **{self.division_name}** a expiré après 3 minutes."
        )
        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.manager.end_invitation(self.captain_id)
        division_role = interaction.guild.get_role(self.division_role_id) if interaction.guild else None
        if not division_role:
            await interaction.response.send_message(
                "Impossible de trouver le rôle de division. Contacte un administrateur.",
                ephemeral=True,
            )
            return

        try:
            await self.member.add_roles(
                division_role,
                reason=f"Invitation acceptée pour {self.division_name}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Je n'ai pas les permissions pour ajouter le rôle de division.",
                ephemeral=True,
            )
            return

        try:
            await self.member.edit(nick=build_nickname(self.member, self.division_name))
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="✅ Invitation acceptée",
            description=(
                f"{self.member.mention} a accepté l'invitation et rejoint **{self.division_name}**."
            ),
            color=discord.Color.green(),
        )
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)
        await self.manager.send_join_announcement(self.member, self.division_name)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="❌")
    async def refuse_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.manager.end_invitation(self.captain_id)
        embed = discord.Embed(
            title="❌ Invitation refusée",
            description=(
                f"{self.member.mention} a refusé l'invitation à **{self.division_name}**."
            ),
            color=discord.Color.red(),
        )
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Bloquer", style=discord.ButtonStyle.secondary, emoji="🚫")
    async def block_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.manager.end_invitation(self.captain_id)
        block_member_from_division(self.member.id, self.division_name)
        
        embed = discord.Embed(
            title="🚫 Division bloquée",
            description=(
                f"{self.member.mention}, tu as bloqué **{self.division_name}**. Tu ne pourras plus recevoir d'invitations de cette division.\n\n"
                f"Pour débloquer, utilise : `d!debloquer {get_division_number(self.division_name)}`"
            ),
            color=discord.Color.dark_red(),
        )
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

class DivisionManager(commands.Cog):
    """Cog de gestion des divisions RP."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_invitations: dict[int, InvitationView] = {}
        self.active_configs: dict[int, dict] = {}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        guild_names = ", ".join(guild.name for guild in self.bot.guilds)
        print(f"[DivisionManager] Prêt. Serveurs connectés: {guild_names}")

    def end_invitation(self, captain_id: int) -> None:
        self.active_invitations.pop(captain_id, None)

    async def send_join_announcement(self, member: discord.Member, division_name: str) -> None:
        data = DIVISIONS[division_name]
        main_channel_id = data["channels"]["main"]
        channel = member.guild.get_channel(main_channel_id)
        if not channel:
            return

        await channel.send(
            f"Bienvenue à {member.mention} dans **{division_name}** ! ``[Div {format_division_prefix(division_name)}]``"
        )

    @commands.command(name="inviter")
    @is_division_captain()
    async def inviter(self, ctx: commands.Context, member: discord.Member) -> None:
        """Invite un membre à rejoindre la division du capitaine."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")

        if member.bot:
            await ctx.reply("Tu ne peux pas inviter un bot.", delete_after=5)
            return

        if member == ctx.author:
            await ctx.reply("Tu ne peux pas t'inviter toi-même.", delete_after=5)
            return

        captain_division = get_division_by_member(ctx.author)
        if not captain_division:
            await ctx.reply(
                "Impossible de déterminer ta division. Assure-toi d'en faire partie.",
                delete_after=5,
            )
            return

        division_name, division_data = captain_division
        
        if is_member_blocked(member.id, division_name):
            await ctx.reply(
                f"Ce membre a bloqué les invitations de **{division_name}**.",
                delete_after=5,
            )
            return

        if any(member.get_role(data["role_id"]) for data in DIVISIONS.values()):
            await ctx.reply(
                "Ce membre appartient déjà à une division.",
                delete_after=5,
            )
            return

        if ctx.author.id in self.active_invitations:
            await ctx.reply(
                "Tu as déjà une invitation active. Attends que celle-ci soit traitée.",
                delete_after=5,
            )
            return

        entrants_channel = ctx.guild.get_channel(division_data["channels"]["entrants"])
        if not entrants_channel:
            await ctx.reply(
                "Impossible de trouver le salon des entrants de ta division.",
                delete_after=5,
            )
            return

        embed = discord.Embed(
            title=f"Invitation pour {division_name}",
            description=(
                f"{member.mention}, tu es invité(e) à rejoindre **{division_name}** par {ctx.author.mention}."
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(name="Validité", value="3 minutes", inline=True)
        embed.add_field(name="Capitaine", value=ctx.author.mention, inline=True)

        view = InvitationView(
            manager=self,
            member=member,
            division_name=division_name,
            division_role_id=division_data["role_id"],
            captain_id=ctx.author.id,
        )

        message = await entrants_channel.send(content=member.mention, embed=embed, view=view)
        view.message = message
        self.active_invitations[ctx.author.id] = view

        await ctx.reply(
            f"Invitation envoyée dans {entrants_channel.mention}. Le membre a 3 minutes pour répondre.",
            delete_after=5,
        )

    @commands.command(name="debloquer")
    async def debloquer(self, ctx: commands.Context, division_num: str) -> None:
        """Débloque une division pour recevoir ses invitations à nouveau."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")

        blocked = get_blocked_divisions(ctx.author.id)
        if not blocked:
            await ctx.reply("Tu n'as bloqué aucune division.", delete_after=5)
            return

        division_name = f"Division {division_num}"
        if division_name not in blocked:
            await ctx.reply(f"Tu n'as pas bloqué **{division_name}**.", delete_after=5)
            return

        unblock_member_from_division(ctx.author.id, division_name)
        await ctx.reply(f"✅ Tu as débloqué **{division_name}**. Tu peux à nouveau recevoir ses invitations.", delete_after=5)

    @commands.command(name="bliste")
    async def bliste(self, ctx: commands.Context) -> None:
        """Affiche la liste des divisions que tu as bloquées."""
        if not ctx.guild:
            raise commands.NoPrivateMessage("Cette commande fonctionne uniquement sur le serveur.")

        blocked = get_blocked_divisions(ctx.author.id)
        if not blocked:
            await ctx.reply("Tu n'as bloqué aucune division.", delete_after=5)
            return

        embed = discord.Embed(
            title="🚫 Divisions bloquées",
            description="\n".join([f"• **{div}** — `d!debloquer {get_division_number(div)}`" for div in blocked]),
            color=discord.Color.dark_red(),
        )
        await ctx.reply(embed=embed, delete_after=30)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CheckFailure) and ctx.command and ctx.command.name == "inviter":
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("⚠️ Il manque un argument requis à la commande.", delete_after=5)
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.reply("⚠️ Cette commande ne peut être utilisée que sur le serveur.", delete_after=5)
        else:
            raise error

def setup(bot: commands.Bot) -> None:
    bot.add_cog(DivisionManager(bot))
