from discord.ext import commands
from bot.config import ADMIN_IDS

def is_admin():
    async def predicate(ctx):
        return ctx.author.id in ADMIN_IDS
    return commands.check(predicate)