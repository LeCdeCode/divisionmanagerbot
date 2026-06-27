import discord
from discord.ext import commands
from discord.ui import View, Select
from typing import Optional

COMMAND_CATEGORIES = {
    "Général": {
        "description": "Commandes utiles pour démarrer et comprendre le bot.",
        "commands": {
            "d!help": "Affiche cette aide interactive. Utilise `d!help <commande>` pour un détail précis.",
            "d!postuler": "Ouvre le menu de recrutement et crée un ticket privé pour postuler.",
            "d!profil": "Affiche ton profil ou celui d'un autre membre.",
            "d!divinfo": "Affiche les informations publiques d'une division.",
        },
    },
    "Recrutement": {
        "description": "Tout ce qui touche aux tickets de candidature et au processus d'entrée.",
        "commands": {
            "d!postuler": "Lance la procédure de candidature et ouvre un ticket privé avec le staff.",
        },
    },
    "Configuration": {
        "description": "Commandes pour créer et ajuster la configuration des divisions.",
        "commands": {
            "d!config": "Démarre la configuration interactive des divisions et enregistre les paramètres.",
        },
    },
    "Gestion": {
        "description": "Commandes réservées au staff pour gérer les recrutements, rangs et bannissements.",
        "commands": {
            "d!inviter": "Invite un membre à rejoindre une division via le système interne.",
            "d!debloquer": "Retire un membre de la liste d'attente ou du blocage d'une division.",
            "d!bliste": "Affiche la liste des membres bloqués dans le système.",
            "d!rank": "Attribue un grade interne à un membre dans une division.",
            "d!unrank": "Retire un grade interne donné précédemment.",
            "d!kick": "Expulse un membre d'une division avec cooldown de réintégration.",
            "d!ban": "Bannit un membre du système de recrutement.",
            "d!deban": "Révoque un bannissement.",
            "d!quitter": "Laisse un membre quitter sa division proprement.",
        },
    },
    "Profil": {
        "description": "Personnalisation et affichage des profils de membre.",
        "commands": {
            "d!profil": "Affiche ou met à jour ton profil et tes informations de division.",
            "d!divinfo": "Affiche les informations d'une division (staff, règles, description).",
        },
    },
}

COMMAND_DETAILS = {
    "d!help": "Utilise `d!help` pour ouvrir l'aide interactive. Avec `d!help <commande>`, tu obtiens une description détaillée et des exemples d'utilisation.",
    "d!postuler": "Lance le menu de recrutement. Tu choisis la division puis un ticket privé est créé. Le staff pourra accepter ou refuser, et un transcript est envoyé à la fermeture.",
    "d!profil": "Affiche ton profil de joueur, ta couleur, ta bio, et tes dates de recrutement. Sans argument, il montre ton profil ; avec un membre, il affiche le sien.",
    "d!divinfo": "Donne un aperçu détaillé d'une division spécifique, y compris le staff et les règles publiques.",
    "d!config": "Démarre l'interface de configuration des divisions. Tu définis les noms, descriptions, canaux, et options puis tu confirmes.",
    "d!inviter": "Le staff peut inviter un membre spécifiquement dans une division. C'est utile pour les recrutements directs.",
    "d!debloquer": "Supprime un membre de la liste de blocage. Utilisé quand un blocage est terminé ou annulé.",
    "d!bliste": "Montre la liste des membres actuellement bloqués et leurs raisons.",
    "d!rank": "Attribue un grade dans une division (lieutenant, vice-capitaine, etc.). Une cooldown s'applique pour les changements fréquents.",
    "d!unrank": "Retire un grade donné à un membre.",
    "d!kick": "Expulse un membre d'une division. Un cooldown de réintégration est automatiquement appliqué.",
    "d!ban": "Bannit un membre du système de recrutement. Utile en cas d'abus ou de triche.",
    "d!deban": "Annule un bannissement et permet au membre de postuler de nouveau.",
    "d!quitter": "Permet à un membre de quitter proprement sa division et d'activer la cooldown de sortie.",
}

class HelpView(View):
    def __init__(self, category: str = "Général", mode: str = "Aperçu"):
        super().__init__(timeout=None)
        self.category = category
        self.mode = mode
        self.add_item(HelpCategorySelect(self))
        self.add_item(HelpModeSelect(self))

    def build_embed(self) -> discord.Embed:
        category = COMMAND_CATEGORIES[self.category]
        embed = discord.Embed(
            title=f"Aide du bot — {self.category}",
            description=category["description"],
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Change le menu déroulant pour voir d'autres sections ou passe en mode détails.")

        if self.mode == "Aperçu":
            for command, summary in category["commands"].items():
                embed.add_field(name=command, value=summary, inline=False)
        else:
            for command, _ in category["commands"].items():
                detail = COMMAND_DETAILS.get(command, "Description détaillée non disponible.")
                embed.add_field(name=command, value=detail, inline=False)

        return embed


class HelpCategorySelect(Select):
    def __init__(self, view: HelpView):
        options = [
            discord.SelectOption(label=name, description=data["description"], value=name)
            for name, data in COMMAND_CATEGORIES.items()
        ]
        super().__init__(placeholder="Choisis une catégorie", min_values=1, max_values=1, options=options)
        self.view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.category = self.values[0]
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class HelpModeSelect(Select):
    def __init__(self, view: HelpView):
        options = [
            discord.SelectOption(label="Aperçu", description="Résumé rapide de chaque commande", value="Aperçu"),
            discord.SelectOption(label="Détails", description="Description approfondie et cas d'usage", value="Détails"),
        ]
        super().__init__(placeholder="Choisis le niveau d'information", min_values=1, max_values=1, options=options)
        self.view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.mode = self.values[0]
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="help", aliases=["aide"])
    async def help_command(self, ctx: commands.Context, command_name: Optional[str] = None) -> None:
        """Affiche l'aide interactive ou les détails d'une commande."""
        if command_name:
            command_key = command_name if command_name.startswith("d!") else f"d!{command_name}"
            detail = COMMAND_DETAILS.get(command_key)
            if not detail:
                await ctx.reply(f"Je ne connais pas la commande `{command_key}`. Essaie `d!help` pour voir toutes les commandes.")
                return

            embed = discord.Embed(
                title=f"Aide détaillée — {command_key}",
                description=detail,
                color=discord.Color.green(),
            )
            embed.add_field(name="Usage", value=f"`{command_key}`", inline=False)
            await ctx.reply(embed=embed)
            return

        view = HelpView()
        embed = view.build_embed()
        await ctx.reply(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
