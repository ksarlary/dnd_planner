from __future__ import annotations
from datetime import datetime
import discord

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