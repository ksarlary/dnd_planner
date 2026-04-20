from discord import app_commands, Interaction
from bot.config import ADMIN_IDS

class AdminOnlyError(app_commands.CheckFailure):
    pass

def is_admin():
    async def predicate(interaction: Interaction) -> bool:
        if interaction.user.id not in ADMIN_IDS:
            raise AdminOnlyError("You must be an admin to use this command.")
        return True

    return app_commands.check(predicate)