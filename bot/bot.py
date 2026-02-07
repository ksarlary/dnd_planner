import os
import re
import random
import logging
import math
import json
from typing import Optional
from datetime import datetime, date, timedelta
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from dotenv import load_dotenv

# -------------------- Env / Logging --------------------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("discord-bot")

if not TOKEN:
    raise SystemExit("DISCORD_TOKEN not set in environment (.env).")

# -------------------- Intents --------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = False  # OK because we use slash commands only

# -------------------- Helpers --------------------

def format_dt(dt: datetime, style: str = "F") -> str:
    try:
        return discord.utils.format_dt(dt, style=style)
    except Exception:
        return str(dt)

def list_roles(member: discord.Member) -> str:
    roles = [r.name for r in member.roles if r.name != "@everyone"]
    return ", ".join(roles) if roles else "None"

STATUSES = [
    "type /help",
    "pinging servers…",
    "planning next dnd session",
]

# -------------------- D&D Planning Storage --------------------

CONFIG_PATH = Path("config.json")
DATA_DIR = Path("data")
DATA_PATH = DATA_DIR / "availability.json"

DAY_NAMES = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError("config.json not found.")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_availability() -> dict:
    if not DATA_PATH.exists():
        return {}
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_availability(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def planning_week_key(today: Optional[date] = None) -> str:
    if today is None:
        today = date.today()
    # Next Monday (always in the future)
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    monday = today + timedelta(days=days_until_monday)
    iso_year, iso_week, _ = monday.isocalendar()
    return f"{iso_year}-W{iso_week}"

def ensure_week(data: dict, week_key: str) -> dict:
    if week_key not in data:
        data[week_key] = {}
    return data[week_key]

def set_availability(week_key: str, user_id: int, day: str, status: str) -> None:
    data = load_availability()
    week = ensure_week(data, week_key)
    user_key = str(user_id)
    if user_key not in week:
        week[user_key] = {}
    week[user_key][day] = status
    save_availability(data)

def summarize_day(week_data: dict, players: list[int], day: str):
    any_not = False
    any_maybe = False
    all_available = True
    details: dict[int, Optional[str]] = {}

    for pid in players:
        ukey = str(pid)
        status = week_data.get(ukey, {}).get(day)
        details[pid] = status

        if status == "not":
            any_not = True
            all_available = False
        elif status == "maybe":
            any_maybe = True
            all_available = False
        elif status == "available":
            pass
        else:
            # no response
            all_available = False

    if any_not:
        overall = "no"
    elif any_maybe:
        overall = "maybe"
    elif all_available and players:
        overall = "yes"
    else:
        overall = "unknown"

    return overall, details

# -------------------- Discord UI (buttons) --------------------

class AvailabilityView(discord.ui.View):
    def __init__(self, week_key: str, *, timeout: float = 6 * 24 * 60 * 60):
        super().__init__(timeout=timeout)
        self.week_key = week_key

        for idx, day in enumerate(DAY_NAMES):
            row = idx // 3
            for status, label, style in [
                ("available", "✅", discord.ButtonStyle.success),
                ("maybe", "❔", discord.ButtonStyle.secondary),
                ("not", "❌", discord.ButtonStyle.danger),
            ]:
                button = discord.ui.Button(
                    label=f"{day[:3].title()} {label}",
                    style=style,
                    custom_id=f"{day}:{status}",
                    row=row,
                )

                async def callback(
                    interaction: discord.Interaction,
                    d=day,
                    s=status,
                ):
                    set_availability(self.week_key, interaction.user.id, d, s)
                    await interaction.response.send_message(
                        f"Set your **{d.title()}** status to **{s}**.",
                        ephemeral=True,
                    )

                button.callback = callback
                self.add_item(button)

# -------------------- Bot --------------------

class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents)
        self.config: Optional[dict] = None

    async def setup_hook(self) -> None:
        # Load config early
        try:
            self.config = load_config()
            log.info("Loaded config.json")
        except Exception:
            log.exception("Failed to load config.json; D&D planning features will not work.")
            self.config = None

        # Sync slash commands
        try:
            await self.tree.sync()
            log.info("Slash commands synced.")
        except Exception:
            log.exception("Error syncing slash commands")

        # Start background tasks
        if not rotate_status.is_running():
            rotate_status.start()
        if not weekly_task.is_running():
            weekly_task.start()

    async def on_connect(self) -> None:
        log.info("Connected to Discord gateway.")

    async def on_disconnect(self) -> None:
        log.warning("Disconnected from gateway.")

bot = Bot()

# -------------------- Background Tasks --------------------

@tasks.loop(minutes=30)
async def rotate_status() -> None:
    try:
        text = random.choice(STATUSES).replace("{guilds}", str(len(bot.guilds)))
        await bot.change_presence(activity=discord.Game(text))
    except Exception:
        log.debug("rotate_status failed", exc_info=True)

@tasks.loop(minutes=1)
async def weekly_task() -> None:
    if not bot.config:
        return

    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute

    organizer_id = int(bot.config["organizer_id"])
    guild_id = int(bot.config["guild_id"])
    channel_id = int(bot.config["channel_id"])
    player_role_id = int(bot.config["player_role_id"])
    ASK_HOUR = int(bot.config.get("ask_hour", 12))
    SUMMARY_HOUR = int(bot.config.get("summary_hour", 20))

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.warning("Guild not found. Check guild_id in config.json")
        return

    ch = guild.get_channel(channel_id)
    if ch is None:
        log.warning("Channel not found. Check channel_id in config.json")
        return

    def get_players_from_role(g: discord.Guild) -> list[int]:
        role = g.get_role(player_role_id)
        if role is None:
            return []
        return [member.id for member in role.members]

    players = get_players_from_role(guild)
    week_key = planning_week_key(now.date())
    week_data = load_availability().get(week_key, {})

    # Saturday at ASK_HOUR:00
    if weekday == 5 and hour == ASK_HOUR and minute == 0:
        role_mention = f"<@&{player_role_id}>"
        today = now.date()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)

        view = AvailabilityView(week_key)
        await ch.send(
            f"{role_mention}\n"
            f"It's time to plan next week's D&D session (week of **{next_monday.isoformat()}**).\n"
            "Use the buttons below to set your availability for each day!",
            view=view,
        )

    # Sunday at SUMMARY_HOUR:00
    elif weekday == 6 and hour == SUMMARY_HOUR and minute == 0:
        embed = discord.Embed(
            title="D&D Availability Summary (next week)",
            description="Legend: ✅ we can play • ❔ maybe • ❌ we don't play",
            timestamp=now,
        )

        for day in DAY_NAMES:
            overall, details = summarize_day(week_data, players, day)

            if overall == "no":
                status_text = "❌ We **don't play** this day (at least one person is not available)."
            elif overall == "maybe":
                status_text = "❔ **Maybe** (no one is 'not available', but at least one person is 'maybe')."
            elif overall == "yes":
                status_text = "✅ We **can play** (everyone who answered is available)."
            else:
                status_text = "⚪ Not enough info yet."

            lines = []
            for pid in players:
                st = details.get(pid)
                emoji = {
                    "available": "✅",
                    "maybe": "❔",
                    "not": "❌",
                    None: "➖",
                }.get(st, "➖")
                lines.append(f"{emoji} <@{pid}>")

            embed.add_field(
                name=day.title(),
                value=status_text + ("\n" + "\n".join(lines) if players else ""),
                inline=False,
            )

        await ch.send(f"<@{organizer_id}> here's the weekly summary:", embed=embed)

@weekly_task.before_loop
async def before_weekly() -> None:
    await bot.wait_until_ready()

# -------------------- Slash Command Error Handler --------------------

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

# -------------------- General Slash Commands --------------------

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
    lat_ms = f"{int(bot.latency * 1000)}ms" if math.isfinite(bot.latency) else "n/a"
    desc = (
        f"**Bot Name:** {b.name}\n"
        f"**Bot ID:** {b.id}\n"
        f"**Guild Count:** {len(bot.guilds)}\n"
        f"**Latency:** {lat_ms}"
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
    bots_count = sum(1 for m in g.members if m.bot) if g.members else 0
    embed.add_field(name="Members", value=str(g.member_count))
    embed.add_field(name="Bots", value=str(bots_count))
    embed.add_field(name="Created", value=format_dt(g.created_at), inline=False)
    await interaction.response.send_message(embed=embed)

# -------------------- D&D Planning Slash Commands --------------------

def organizer_only(interaction: discord.Interaction) -> bool:
    if not bot.config:
        return False
    return interaction.user.id == int(bot.config["organizer_id"])

@bot.tree.command(name="ask", description="Ask players to set availability for next week (organizer only)")
@app_commands.check(organizer_only)
async def ask(interaction: discord.Interaction):
    if not bot.config:
        return await interaction.response.send_message("Config not loaded.", ephemeral=True)

    player_role_id = int(bot.config["player_role_id"])
    week_key = planning_week_key(date.today())
    role_mention = f"<@&{player_role_id}>"
    view = AvailabilityView(week_key)

    await interaction.response.send_message(
        f"{role_mention}\nManual reminder to set your availability for the upcoming D&D session!",
        view=view,
    )

@bot.tree.command(name="choose_day", description="Choose the final D&D day for next week (organizer only)")
@app_commands.check(organizer_only)
@app_commands.describe(day="monday/tuesday/.../sunday")
async def choose_day(interaction: discord.Interaction, day: str):
    if not bot.config:
        return await interaction.response.send_message("Config not loaded.", ephemeral=True)

    organizer_id = int(bot.config["organizer_id"])
    guild_id = int(bot.config["guild_id"])
    player_role_id = int(bot.config["player_role_id"])

    day = day.lower()
    if day not in DAY_NAMES:
        return await interaction.response.send_message(
            f"Unknown day '{day}'. Use one of: " + ", ".join(DAY_NAMES),
            ephemeral=True,
        )

    guild = bot.get_guild(guild_id) or interaction.guild
    if guild is None:
        return await interaction.response.send_message("Guild not found.", ephemeral=True)

    role = guild.get_role(player_role_id)
    players = [m.id for m in role.members] if role else []

    week_key = planning_week_key(date.today())
    week_data = load_availability().get(week_key, {})
    overall, details = summarize_day(week_data, players, day)

    if overall == "no":
        verdict = "❌ We **don't play** on this day (someone is not available)."
    elif overall == "maybe":
        verdict = "❔ It's a **maybe**. Some people marked 'maybe' and no one is 'not available'."
    elif overall == "yes":
        verdict = "✅ We **play** on this day! Everyone who answered is available."
    else:
        verdict = "⚪ Not enough information to decide."

    lines = []
    for pid in players:
        st = details.get(pid)
        emoji = {
            "available": "✅",
            "maybe": "❔",
            "not": "❌",
            None: "➖",
        }.get(st, "➖")
        lines.append(f"{emoji} <@{pid}>")

    await interaction.response.send_message(
        f"<@{organizer_id}> has selected **{day.title()}** for D&D.\n"
        f"{verdict}\n\n"
        + ("\n".join(lines) if lines else "No players in the role yet.")
    )

# -------------------- Main --------------------

if __name__ == "__main__":
    log.info("Starting bot…")
    bot.run(TOKEN)
