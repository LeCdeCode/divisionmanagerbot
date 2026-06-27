import os
import discord
from discord.ext import commands
from discord.ui import Modal, TextInput
from typing import Optional
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", str(Path(__file__).parent.parent / "data"))))
DATA_DIR.mkdir(parents=True, exist_ok=True)

class ConfigNameModal(Modal, title="Nom de la division"):
    custom_name = TextInput(
        label="Nom personnalisé (optionnel, sinon Division [numéro])",
        placeholder="Ex: Shinigami Corps Division 1",
        max_length=100,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

class ConfigDescriptionModal(Modal, title="Description de la division"):
    description = TextInput(
        label="Description (optionnel)",
        placeholder="Décris ta division...",
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

class ConfigAgeModal(Modal, title="Âge minimum"):
    min_age = TextInput(
        label="Âge minimum requis (optionnel, skip si aucun)",
        placeholder="Ex: 13",
        max_length=3,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

class ConfigRulesModal(Modal, title="Règlement interne"):
    rules = TextInput(
        label="Règlement interne (optionnel)",
        placeholder="Énonce les règles...",
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
