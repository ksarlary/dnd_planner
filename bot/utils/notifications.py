import logging
from collections.abc import Awaitable, Callable

import discord

from bot.storage.notifications import (
    allows_availability_reminders,
    allows_planned_session_messages,
    allows_session_reminders,
)

log = logging.getLogger("discord-bot")

NotificationPreference = Callable[[int], bool]


async def send_dm_if_allowed(
    client: discord.Client,
    user_id: int,
    is_allowed: NotificationPreference,
    send_message: Callable[[discord.User], Awaitable[None]],
) -> bool:
    if not is_allowed(user_id):
        return False

    try:
        user = client.get_user(user_id) or await client.fetch_user(user_id)
        await send_message(user)
        return True
    except Exception:
        log.exception("Failed to send notification DM to user_id=%s", user_id)
        return False


async def send_availability_reminder_dm(
    client: discord.Client,
    user_id: int,
    send_message: Callable[[discord.User], Awaitable[None]],
) -> bool:
    return await send_dm_if_allowed(
        client,
        user_id,
        allows_availability_reminders,
        send_message,
    )


async def send_session_reminder_dm(
    client: discord.Client,
    user_id: int,
    send_message: Callable[[discord.User], Awaitable[None]],
) -> bool:
    return await send_dm_if_allowed(
        client,
        user_id,
        allows_session_reminders,
        send_message,
    )


async def send_planned_session_message_dm(
    client: discord.Client,
    user_id: int,
    send_message: Callable[[discord.User], Awaitable[None]],
) -> bool:
    return await send_dm_if_allowed(
        client,
        user_id,
        allows_planned_session_messages,
        send_message,
    )
