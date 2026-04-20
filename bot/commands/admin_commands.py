from discord.ext import commands
from bot.utils.checks import is_admin

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @is_admin()
    async def force_schedule(self, ctx):
        await ctx.send("Admin verified. Generating session plan...")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))