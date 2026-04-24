import logging
import random

import discord
from discord.ext import tasks

from bot.config import ADMIN_IDS
from bot.storage.planning import (
    get_players_with_missing_availabilities,
    get_planning_started_at,
    get_planning_week_notification_states,
    get_planning_target_weeks,
    get_registered_players,
    get_sessions_needing_day_before_reminder,
    mark_planning_week_notification_sent,
    mark_planning_reminder_sent,
    mark_session_day_before_reminder_sent,
    was_planning_reminder_sent,
)
from bot.ui.availability_view import (
    PublicAvailabilityView,
    build_missing_availability_reminder_embed,
    build_session_day_before_reminder_embed,
)
from bot.utils.availability_summary import build_week_availability_summary_embed
from bot.utils.planning import get_availability_slots
from bot.utils.time import now
from bot.utils.utils import STATUSES

log = logging.getLogger("discord-bot")

def setup_tasks(bot) -> None:
    @tasks.loop(minutes=30)
    async def rotate_status() -> None:
        try:
            text = random.choice(STATUSES).replace("{guilds}", str(len(bot.guilds)))
            await bot.change_presence(activity=discord.Game(text))
        except Exception:
            log.debug("rotate_status failed", exc_info=True)

    bot.rotate_status = rotate_status

    if not bot.rotate_status.is_running():
        bot.rotate_status.start()

    @tasks.loop(minutes=1)
    async def notify_admins_after_planning_deadline() -> None:
        try:
            current_time = now()
            target_weeks = get_planning_week_notification_states()
            for target_week in target_weeks:
                deadline = target_week["deadline"]
                notification_sent_at = target_week["notification_sent_at"]
                if deadline is None or notification_sent_at is not None:
                    continue
                if current_time <= deadline:
                    continue

                for admin_id in ADMIN_IDS:
                    try:
                        admin_user = bot.get_user(admin_id) or await bot.fetch_user(admin_id)
                        await admin_user.send(
                            embed=build_week_availability_summary_embed(
                                target_week["week_index"]
                            )
                        )
                    except Exception:
                        log.exception("Failed to send planning summary to admin_id=%s", admin_id)

                mark_planning_week_notification_sent(target_week["week_index"])
                log.info("Planning summary notification sent for week_index=%s", target_week["week_index"])
        except Exception:
            log.exception("notify_admins_after_planning_deadline failed")

    @notify_admins_after_planning_deadline.before_loop
    async def before_notify_admins_after_planning_deadline() -> None:
        await bot.wait_until_ready()

    bot.notify_admins_after_planning_deadline = notify_admins_after_planning_deadline

    if not bot.notify_admins_after_planning_deadline.is_running():
        bot.notify_admins_after_planning_deadline.start()

    @tasks.loop(minutes=1)
    async def remind_players_about_missing_availabilities() -> None:
        try:
            current_time = now()
            if current_time.hour != 10:
                return

            started_at = get_planning_started_at()
            slots = []
            open_target_weeks = [
                target_week
                for target_week in get_planning_target_weeks()
                if target_week["deadline"] is not None
                and current_time <= target_week["deadline"]
            ]
            if not open_target_weeks:
                return

            deadline = max(target_week["deadline"] for target_week in open_target_weeks)
            for target_week in open_target_weeks:
                slots.extend(
                    get_availability_slots(started_at, target_week["week_index"])
                )
            slot_labels = dict(slots)
            required_slot_keys = [slot_key for slot_key, label in slots]
            reminder_date = current_time.date()

            for player in get_players_with_missing_availabilities(required_slot_keys):
                user_id = player["user_id"]
                if was_planning_reminder_sent(user_id, reminder_date):
                    continue

                missing_labels = [
                    slot_labels[slot_key]
                    for slot_key in player["missing_slot_keys"]
                    if slot_key in slot_labels
                ]

                try:
                    user = bot.get_user(user_id) or await bot.fetch_user(user_id)
                    await user.send(
                        embed=build_missing_availability_reminder_embed(
                            deadline,
                            missing_labels,
                        ),
                        view=PublicAvailabilityView(),
                    )
                except Exception:
                    log.exception(
                        "Failed to send availability reminder to user_id=%s",
                        user_id,
                    )
                finally:
                    mark_planning_reminder_sent(user_id, reminder_date)
        except Exception:
            log.exception("remind_players_about_missing_availabilities failed")

    @remind_players_about_missing_availabilities.before_loop
    async def before_remind_players_about_missing_availabilities() -> None:
        await bot.wait_until_ready()

    bot.remind_players_about_missing_availabilities = remind_players_about_missing_availabilities

    if not bot.remind_players_about_missing_availabilities.is_running():
        bot.remind_players_about_missing_availabilities.start()

    @tasks.loop(minutes=1)
    async def remind_players_about_tomorrow_sessions() -> None:
        try:
            current_time = now()
            if current_time.hour != 10:
                return

            sessions = get_sessions_needing_day_before_reminder(current_time)
            if not sessions:
                return

            players = get_registered_players()
            for session in sessions:
                embed = build_session_day_before_reminder_embed(session["slot_label"])
                for player in players:
                    user_id = player["user_id"]
                    try:
                        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
                        await user.send(embed=embed)
                    except Exception:
                        log.exception(
                            "Failed to send session reminder to user_id=%s",
                            user_id,
                        )

                mark_session_day_before_reminder_sent(session["slot_key"])
        except Exception:
            log.exception("remind_players_about_tomorrow_sessions failed")

    @remind_players_about_tomorrow_sessions.before_loop
    async def before_remind_players_about_tomorrow_sessions() -> None:
        await bot.wait_until_ready()

    bot.remind_players_about_tomorrow_sessions = remind_players_about_tomorrow_sessions

    if not bot.remind_players_about_tomorrow_sessions.is_running():
        bot.remind_players_about_tomorrow_sessions.start()
