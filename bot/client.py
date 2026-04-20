import logging
from discord.ext import commands

from bot.errors import setup_error_handler
from bot.tasks import setup_tasks
from bot.commands.basic import setup_basic_commands
from bot.commands.admin import setup_admin_commands

log = logging.getLogger("discord-bot")

class Bot(commands.Bot):
    def __init__(self, *, intents):
        super().__init__(
            command_prefix="/",
            intents=intents
        )

    async def setup_hook(self) -> None:
        setup_error_handler(self)
        setup_tasks(self)
        setup_basic_commands(self)
        setup_admin_commands(self)

        try:
            await self.tree.sync()
            log.info("Slash commands synced.")
        except Exception:
            log.exception("Error syncing commands")