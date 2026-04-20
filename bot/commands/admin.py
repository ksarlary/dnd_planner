import discord
from discord import app_commands

from bot.utils.checks import is_admin

def setup_admin_commands(bot) -> None:
    @bot.tree.command(name="admin_ping", description="Admin-only test command")
    @is_admin()
    async def admin_ping(interaction: discord.Interaction):
        await interaction.response.send_message("Admin command works", ephemeral=True)