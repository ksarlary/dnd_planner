import logging
from discord.ext import commands

from bot.errors import setup_error_handler
from bot.tasks import setup_tasks
from bot.commands.basic import setup_basic_commands
from bot.commands.fun import setup_fun_commands
from bot.commands.profile import setup_profile_commands
from bot.commands.admin import setup_admin_commands
from bot.commands.planning import setup_planning_commands
from bot.storage.db import init_db
from bot.ui.availability_view import PublicAvailabilityView

log = logging.getLogger("discord-bot")

class Bot(commands.Bot):
    def __init__(self, *, intents):
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self) -> None:
        log.info("setup_hook started")

        init_db()
        log.info("database initialized")

        self.add_view(PublicAvailabilityView())
        log.info("persistent views loaded")

        setup_error_handler(self)
        log.info("error handler loaded")

        setup_tasks(self)
        log.info("tasks loaded")

        setup_basic_commands(self)
        log.info("basic commands loaded")

        setup_fun_commands(self)
        log.info("fun commands loaded")

        setup_profile_commands(self)
        log.info("profile commands loaded")

        setup_admin_commands(self)
        log.info("admin commands loaded")
        
        setup_planning_commands(self)
        log.info("planning commands loaded")

        try:
            synced = await self.tree.sync()
            log.info("Slash commands synced: %s", [cmd.name for cmd in synced])
        except Exception:
            log.exception("Error syncing commands")
