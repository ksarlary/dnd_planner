import logging
import random
import discord
from discord.ext import tasks

from bot.utils.utils import STATUSES

log = logging.getLogger("discord-bot")

def setup_tasks(bot) -> None:
    @tasks.loop(minutes=30)
    async def rotate_status() -> None:
        try:
            text = random.choice(STATUSES).replace("{guilds}", str(len(bot.guilds)))
            await bot.change_presence(activity=discord.Game(text))
        except Exception:
            log.debug("rotate_status failed", exc_info=True)

    bot.rotate_status = rotate_status

    if not bot.rotate_status.is_running():
        bot.rotate_status.start()