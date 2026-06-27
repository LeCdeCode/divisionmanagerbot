import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Button
from typing import Optional
import json
from pathlib import Path
from datetime import datetime, timedelta
import re

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
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

class ConfigNameModal(Modal, title="Nom personnalisé"):
    name_input = TextInput(
        label="Nom de la division",
        placeholder="Ex: Shinigami Corps Division 1",
        max_length=100,
        required=False,
    )
    
    def __init__(self, view: "ConfigSetupView"):
        super().__init__()
        self.view = view
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.view.config["custom_name"] = self.name_input.value or None
        await interaction.response.defer()

class ConfigDescriptionModal(Modal, title="Description"):
    desc_input = TextInput(
        label="Description de ta division",
        placeholder="Décris ta division...",
        max_length=500,
        required=False,
    )
    
    def __init__(self, view: "ConfigSetupView"):
        super().__init__()
        self.view = view
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.view.config["description"] = self.desc_input.value or None
        await interaction.response.defer()

class ConfigAgeModal(Modal, title="Âge minimum"):
    age_input = TextInput(
        label="Âge minimum requis (laisser vide pour aucun)",
        placeholder="Ex: 13",
        max_length=3,
        required=False,
    )
    
    def __init__(self, view: "ConfigSetupView"):
        super().__init__()
        self.view = view
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        age_value = self.age_input.value
        if age_value:
            try:
                int(age_value)
                self.view.config["min_age"] = age_value
            except ValueError:
                self.view.config["min_age"] = None
        else:
            self.view.config["min_age"] = None
        await interaction.response.defer()

class ConfigRulesModal(Modal, title="Règlement"):
    rules_input = TextInput(
        label="Règlement interne (optionnel)",
        placeholder="Énonce les règles...",
        max_length=500,
        required=False,
    )
    
    def __init__(self, view: "ConfigSetupView"):
        super().__init__()
        self.view = view
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.view.config["rules"] = self.rules_input.value or None
        await interaction.response.defer()

class ConfigColorsModal(Modal, title="Couleurs du rôle"):
    color1_input = TextInput(
        label="Première couleur (hex, ex: FF0000)",
        placeholder="FF0000",
        max_length=6,
        required=False,
    )
    color2_input = TextInput(
        label="Deuxième couleur pour dégradé (hex)",
        placeholder="00FF00",
        max_length=6,
        required=False,
    )
    
    def __init__(self, view: "ConfigSetupView"):
        super().__init__()
        self.view = view
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        color1 = self.color1_input.value
        color2 = self.color2_input.value
        
        if color1 and len(color1) == 6:
            try:
                int(color1, 16)
                self.view.config["role_color1"] = color1
            except ValueError:
                pass
        
        if color2 and len(color2) == 6:
            try:
                int(color2, 16)
                self.view.config["role_color2"] = color2
            except ValueError:
                pass
        
        await interaction.response.defer()

class ConfigSetupView(View):
    def __init__(self, captain: discord.Member, division_name: str, manager: "ConfigManager") -> None:
        super().__init__(timeout=600.0)
        self.captain = captain
        self.division_name = division_name
        self.manager = manager
        self.step = 1
        self.config = load_division_config(division_name) or {
            "custom_name": None,
            "description": None,
            "min_age": None,
            "rules": None,
            "profile_url": None,
            "banner_url": None,
            "role_color1": None,
            "role_color2": None,
            "role_badge": None,
        }
        self.message: Optional[discord.Message] = None
    
    async def update_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"⚙️ Configuration - Division {get_division_number(self.division_name)}",
            color=discord.Color.blue(),
        )
        
        step_titles = {
            1: "📝 Nom personnalisé",
            2: "📄 Description",
            3: "📅 Âge minimum",
            4: "📋 Règlement",
            5: "🖼️ Image de profil",
            6: "🎨 Bannière",
            7: "🎨 Couleurs du rôle",
            8: "✨ Badge du rôle",
        }
        
        embed.description = f"**Étape {self.step}/8** : {step_titles.get(self.step, 'Configuration')}"
        
        fields = [
            ("Nom", self.config.get("custom_name") or f"Division {get_division_number(self.division_name)}"),
            ("Description", self.config.get("description") or "Aucune"),
            ("Âge minimum", self.config.get("min_age") or "Aucun"),
            ("Règlement", self.config.get("rules") or "Aucun"),
        ]
        
        for name, value in fields:
            embed.add_field(name=name, value=value or "Non configuré", inline=False)
        
        return embed
    
    async def show_current_step(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        
        if self.step == 1:
            modal = ConfigNameModal(self)
            await interaction.followup.send_modal(modal)
        elif self.step == 2:
            modal = ConfigDescriptionModal(self)
            await interaction.followup.send_modal(modal)
        elif self.step == 3:
            modal = ConfigAgeModal(self)
            await interaction.followup.send_modal(modal)
        elif self.step == 4:
            modal = ConfigRulesModal(self)
            await interaction.followup.send_modal(modal)
        elif self.step == 5:
            await interaction.followup.send("📤 Envoie une image pour la PP (ou tape `skip`)...", ephemeral=True)
        elif self.step == 6:
            await interaction.followup.send("📤 Envoie une image pour la bannière (ou tape `skip`)...", ephemeral=True)
        elif self.step == 7:
            modal = ConfigColorsModal(self)
            await interaction.followup.send_modal(modal)
        elif self.step == 8:
            await interaction.followup.send("✨ Envoie un emoji ou une image pour le badge (ou tape `skip`)...", ephemeral=True)
        
        embed = await self.update_embed()
        
        self.clear_items()
        
        if self.step > 1:
            btn_back = Button(label="← Retour", style=discord.ButtonStyle.gray)
            btn_back.callback = self.back_callback
            self.add_item(btn_back)
        
        if self.step < 8:
            btn_skip = Button(label="⏭️ Passer", style=discord.ButtonStyle.secondary)
            btn_skip.callback = self.skip_callback
            self.add_item(btn_skip)
        
        if self.step < 8:
            btn_next = Button(label="Suivant →", style=discord.ButtonStyle.primary)
            btn_next.callback = self.next_callback
            self.add_item(btn_next)
        else:
            btn_preview = Button(label="📊 Aperçu", style=discord.ButtonStyle.primary)
            btn_preview.callback = self.preview_callback
            self.add_item(btn_preview)
        
        btn_cancel = Button(label="❌ Annuler", style=discord.ButtonStyle.red)
        btn_cancel.callback = self.cancel_callback
        self.add_item(btn_cancel)
        
        if not self.message:
            self.message = await interaction.channel.send(embed=embed, view=self)
        else:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass
    
    async def back_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.captain.id:
            await interaction.response.send_message("Seul le capitaine peut configurer.", ephemeral=True)
            return
        
        if self.step > 1:
            self.step -= 1
            await self.show_current_step(interaction)
    
    async def skip_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.captain.id:
            await interaction.response.send_message("Seul le capitaine peut configurer.", ephemeral=True)
            return
        
        if self.step < 8:
            self.step += 1
            await self.show_current_step(interaction)
    
    async def next_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.captain.id:
            await interaction.response.send_message("Seul le capitaine peut configurer.", ephemeral=True)
            return
        
        if self.step < 8:
            self.step += 1
            await self.show_current_step(interaction)
    
    async def preview_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.captain.id:
            await interaction.response.send_message("Seul le capitaine peut configurer.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        embed = discord.Embed(
            title=self.config.get("custom_name") or f"Division {get_division_number(self.division_name)}",
            description=self.config.get("description") or "Aucune description",
            color=discord.Color.gold(),
        )
        
        if self.config.get("min_age"):
            embed.add_field(name="Âge minimum", value=f"{self.config['min_age']} ans", inline=True)
        
        if self.config.get("rules"):
            embed.add_field(name="Règlement", value=self.config["rules"], inline=False)
        
        if self.config.get("profile_url"):
            embed.set_thumbnail(url=self.config["profile_url"])
        
        if self.config.get("banner_url"):
            embed.set_image(url=self.config["banner_url"])
        
        self.clear_items()
        
        btn_back = Button(label="← Modifier", style=discord.ButtonStyle.gray)
        btn_back.callback = self.back_to_config_callback
        self.add_item(btn_back)
        
        btn_confirm = Button(label="✅ Confirmer", style=discord.ButtonStyle.success)
        btn_confirm.callback = self.confirm_callback
        self.add_item(btn_confirm)
        
        btn_cancel = Button(label="❌ Annuler", style=discord.ButtonStyle.red)
        btn_cancel.callback = self.cancel_callback
        self.add_item(btn_cancel)
        
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass
    
    async def back_to_config_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.captain.id:
            await interaction.response.send_message("Seul le capitaine peut configurer.", ephemeral=True)
            return
        
        self.step = 1
        await self.show_current_step(interaction)
    
    async def confirm_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.captain.id:
            await interaction.response.send_message("Seul le capitaine peut confirmer.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        save_division_config(self.division_name, self.config)
        set_cooldown(interaction.user.id, self.division_name)
        
        guild = interaction.guild
        if guild:
            division_data = DIVISIONS.get(self.division_name)
            if division_data:
                role = guild.get_role(division_data["role_id"])
                if role and self.config.get("role_color1"):
                    try:
                        color_int = int(self.config["role_color1"], 16)
                        await role.edit(color=discord.Color(color_int))
                    except (ValueError, discord.Forbidden):
                        pass
        
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="✅ Configuration sauvegardée",
            description=f"La configuration de **{self.division_name}** a été mise à jour avec succès.\n⏱️ Prochaine modification possible dans 7 jours.",
            color=discord.Color.green(),
        )
        
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass
        
        self.stop()
    
    async def cancel_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.captain.id:
            await interaction.response.send_message("Seul le capitaine peut annuler.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="❌ Configuration annulée",
            description="Tu as annulé la configuration.",
            color=discord.Color.red(),
        )
        
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass
        
        self.stop()

class ConfigManager(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="config")
    async def config(self, ctx: commands.Context) -> None:
        """Configure le profil de ta division."""
        if not ctx.guild:
            await ctx.reply("⚠️ Cette commande fonctionne uniquement sur le serveur.", delete_after=5)
            return
        
        if not ctx.author.get_role(DIVISION_CAPTAIN_ROLE_ID):
            return
        
        captain_division = get_division_by_member(ctx.author)
        if not captain_division:
            await ctx.reply("Impossible de déterminer ta division.", delete_after=5)
            return
        
        division_name, _ = captain_division
        
        cooldown_remaining = check_cooldown(ctx.author.id, division_name, 7)
        if cooldown_remaining:
            time_left = cooldown_remaining - datetime.now()
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            await ctx.reply(
                f"⏳ Tu pourras modifier ta config dans {hours}h {minutes}m.",
                delete_after=5
            )
            return
        
        view = ConfigSetupView(ctx.author, division_name, self)
        embed = await view.update_embed()
        
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        
        await view.show_current_step(ctx)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(ConfigManager(bot))
