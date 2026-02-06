import os
import re
import random
import logging
import math
from typing import Optional
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("discord-bot")

if not TOKEN:
    raise SystemExit("DISCORD_TOKEN not set in environment (.env).")

intents = discord.Intents.default()
intents.members = True


class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="/", intents=intents)

    async def on_connect(self) -> None:
        log.info("Connected to Discord gateway.")

    async def on_disconnect(self) -> None:
        log.warning("Disconnected from gateway.")

    async def setup_hook(self) -> None:
        
        try:
            await self.tree.sync()
            log.info("Slash commands synced.")
        except Exception:
            log.exception("Error syncing commands")

        if not rotate_status.is_running():
            rotate_status.start()

        lat = getattr(self, "latency", float("nan"))
        lat_ms = f"{int(lat * 1000)}ms" if isinstance(lat, (int, float)) and math.isfinite(lat) else "n/a"
        log.info(
            "Logged in as %s (%s) | guilds=%d | latency=%s",
            self.user, getattr(self.user, "id", "?"), len(self.guilds), lat_ms
        )


bot = Bot()

def format_dt(dt: datetime, style: str = "F") -> str:
    try:
        return discord.utils.format_dt(dt, style=style)
    except Exception:
        return str(dt)


def list_roles(member: discord.Member) -> str:
    roles = [r.name for r in member.roles if r.name != "@everyone"]
    return ", ".join(roles) if roles else "None"


STATUSES = [
    "with /help",
    "pinging servers…",
    "type /trivia",
]


@tasks.loop(minutes=30)
async def rotate_status() -> None:
    try:
        text = random.choice(STATUSES).replace("{guilds}", str(len(bot.guilds)))
        await bot.change_presence(activity=discord.Game(text))
    except Exception:
        log.debug("rotate_status failed", exc_info=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    async def _safe_respond(content: str, ephemeral: bool = False):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(content, ephemeral=ephemeral)
        except Exception:
            pass

    if isinstance(error, app_commands.CommandOnCooldown):
        return await _safe_respond(f"⏳ Slow down! Try again in {error.retry_after:.1f}s.", ephemeral=True)

    if isinstance(error, app_commands.CheckFailure):
        return await _safe_respond("🚫 You don't have permission to use this command here.", ephemeral=True)

    log.exception("Unhandled app command error (%s)", interaction.command)
    await _safe_respond("⚠️ Something went wrong. It’s been logged.", ephemeral=True)


@bot.tree.command(name="hello", description="Greet the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hello from the bot! 👋")


@bot.tree.command(name="ping", description="Check if the bot is responsive")
async def ping(interaction: discord.Interaction):
    lat = getattr(bot, "latency", float("nan"))
    lat_ms = f"{int(lat * 1000)}ms" if isinstance(lat, (int, float)) and math.isfinite(lat) else "n/a"
    await interaction.response.send_message(f"Pong! 🏓 `{lat_ms}`")


@bot.tree.command(name="info", description="Get information about the bot")
async def info(interaction: discord.Interaction):
    b = bot.user
    if b is None:
        return await interaction.response.send_message("Bot user not ready yet.", ephemeral=True)
    desc = (
        f"**Bot Name:** {b.name}\n"
        f"**Bot ID:** {b.id}\n"
        f"**Guild Count:** {len(bot.guilds)}\n"
        f"**Latency:** {lat_ms if (lat_ms := (f"{int(bot.latency * 1000)}ms" if math.isfinite(bot.latency) else 'n/a')) else 'n/a'}"
    )
    await interaction.response.send_message(desc)


@bot.tree.command(name="user", description="Get information about a user")
@app_commands.describe(member="The user to inspect (optional)")
async def user(interaction: discord.Interaction, member: Optional[discord.Member] = None):
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


@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    lines = []
    for c in bot.tree.walk_commands():
        if isinstance(c, app_commands.Command):
            desc = c.description or "—"
            lines.append(f"/{c.name} — {desc}")
    lines.sort()

    text = "\n".join(lines)
    if len(text) > 1900:
        text = text[:1900] + "\n…"

    embed = discord.Embed(title="Help — Available Commands", description=text, color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)


ROLL_RE = re.compile(r"^\s*(\d+)d(\d+)([+-]\d+)?\s*$")


@app_commands.describe(dice="e.g. 1d20, 2d6+3", secret="Send result as ephemeral")
@app_commands.checks.cooldown(1, 3.0, key=lambda i: i.user.id)
@bot.tree.command(name="roll", description="Roll dice in XdY(+/-Z) format")
async def roll(interaction: discord.Interaction, dice: str, secret: bool = False):
    m = ROLL_RE.fullmatch(dice)
    if not m:
        return await interaction.response.send_message("Format: `XdY+Z` (e.g., `2d6+1`)", ephemeral=True)

    x, y, mod = int(m[1]), int(m[2]), int(m[3] or 0)
    if not (1 <= x <= 100) or not (2 <= y <= 1000):
        return await interaction.response.send_message("Dice bounds: `1≤X≤100`, `2≤Y≤1000`.", ephemeral=True)

    rolls = [random.randint(1, y) for _ in range(x)]
    total = sum(rolls) + mod
    sign = "+" if mod >= 0 else ""
    msg = f"🎲 `{dice}` → {rolls} {sign}{mod} = **{total}**"
    await interaction.response.send_message(msg, ephemeral=secret)


@bot.tree.context_menu(name="Get Avatar")
async def ctx_avatar(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(member.display_avatar.url, ephemeral=True)


@bot.tree.command(name="avatar", description="Show a user's avatar")
@app_commands.describe(member="The user (optional)")
async def avatar(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    m = member or interaction.user
    await interaction.response.send_message(m.display_avatar.url)


@bot.tree.command(name="server", description="Show information about this server")
async def server(interaction: discord.Interaction):
    g = interaction.guild
    if not g:
        return await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)

    embed = discord.Embed(title=g.name, color=discord.Color.teal())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    bots = sum(1 for m in g.members if m.bot) if g.members else 0
    embed.add_field(name="Members", value=str(g.member_count))
    embed.add_field(name="Bots", value=str(bots))
    embed.add_field(name="Created", value=format_dt(g.created_at), inline=False)
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    log.info("Starting bot…")
    bot.run(TOKEN)
