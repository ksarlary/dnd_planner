import math
import logging
import discord
from discord import app_commands
from bot.utils.utils import format_dt, list_roles

log = logging.getLogger("discord-bot")

def setup_basic_commands(bot) -> None:
    @bot.tree.command(name="hello", description="Greet the bot")
    async def hello(interaction: discord.Interaction):
        await interaction.response.send_message("Hello from the bot! 👋")

    @bot.tree.command(name="ping", description="Check if the bot is responsive")
    async def ping(interaction: discord.Interaction):
        lat = getattr(bot, "latency", float("nan"))
        lat_ms = f"{int(lat * 1000)}ms" if isinstance(lat, (int, float)) and math.isfinite(lat) else "n/a"
        await interaction.response.send_message(f"Pong! 🏓 `{lat_ms}`")

    @bot.tree.command(name="user", description="Get information about a user")
    @app_commands.describe(member="The user to inspect (optional)")
    async def user(interaction: discord.Interaction, member: discord.Member | None = None):
        m = member or interaction.user
        embed = discord.Embed(title=f"User info — {m}", color=discord.Color.blurple())
        embed.set_thumbnail(url=m.display_avatar.url)
        embed.add_field(name="User ID", value=str(m.id))
        if hasattr(m, "joined_at") and m.joined_at:
            embed.add_field(name="Joined Server", value=format_dt(m.joined_at), inline=False)
        embed.add_field(name="Account Created", value=format_dt(m.created_at), inline=False)
        embed.add_field(name="Status", value=str(getattr(m, "status", "unknown")).title())
        embed.add_field(name="Roles", value=(list_roles(m)[:1024] or "None"), inline=False)
        await interaction.response.send_message(embed=embed)