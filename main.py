import os
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from aiohttp import web

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Le jeton du bot est manquant dans le fichier .env (BOT_TOKEN).")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("divisionmanagerbot")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="d!", intents=intents, help_command=None)


@bot.event
async def on_ready() -> None:
    logger.info("Bot connecté en tant que %s", bot.user)
    logger.info("Serveurs : %s", ", ".join(guild.name for guild in bot.guilds))


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        await ctx.reply("Commande inconnue. Utilise `d!inviter @membre` pour démarrer une invitation.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"Cette commande est en recharge. Essaie de nouveau dans {error.retry_after:.1f}s.")
    else:
        raise error


def load_extensions() -> None:
    cogs_path = Path(__file__).parent / "cogs"
    for path in cogs_path.glob("*.py"):
        if path.name == "__init__.py":
            continue
        extension_name = f"cogs.{path.stem}"
        try:
            bot.load_extension(extension_name)
            logger.info("Extension chargée : %s", extension_name)
        except Exception:
            logger.exception("Impossible de charger l'extension %s", extension_name)


if __name__ == "__main__":
    load_extensions()
    # Optional keep-alive webserver for environments that require pinging (e.g., some free hosts)
    keep_alive = os.getenv("KEEP_ALIVE", "false").lower() in ("1", "true", "yes")
    if keep_alive:
        async def _handle(request):
            return web.Response(text="ok")

        async def start_webserver():
            port = int(os.getenv("PORT", 8080))
            app = web.Application()
            app.add_routes([web.get("/", _handle)])
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()

        try:
            bot.loop.create_task(start_webserver())
            logger.info("Keep-alive webserver scheduled on port %s", os.getenv("PORT", 8080))
        except Exception:
            logger.exception("Impossible de démarrer le serveur keep-alive")
    bot.run(BOT_TOKEN)
