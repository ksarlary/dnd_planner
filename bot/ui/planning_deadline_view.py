import logging
from datetime import datetime, time

import discord

from bot.storage.planning import get_registered_players, set_planning_deadline
from bot.ui.availability_view import (
    PublicAvailabilityView,
    build_player_availability_invite_embed,
    build_public_availability_embed,
)
from bot.utils.planning import (
    get_deadline_days_before_target_week,
    get_target_week_label,
    get_target_week_start,
    get_upcoming_week_days,
)

log = logging.getLogger("discord-bot")


class DeadlineButton(discord.ui.Button):
    def __init__(self, day: datetime):
        self.day = day

        label = day.strftime("%a %d/%m")
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        deadline = datetime.combine(self.day.date(), time(hour=23, minute=59))
        week_1_label = _target_week_label(1)

        log.info(
            "Planning deadline chosen by user_id=%s as %s",
            interaction.user.id,
            deadline.isoformat(),
        )

        embed = discord.Embed(
            title="🗓️ Choose planning weeks",
            description=(
                f"⏳ {week_1_label} deadline: **{deadline.strftime('%A %d/%m at %H:%M')}**\n"
                "Choose whether players should fill one target week or two. 🎲"
            ),
            color=discord.Color.orange(),
        )

        await interaction.response.edit_message(
            embed=embed,
            view=PlanningWeekCountView(deadline),
        )


class WeekCountButton(discord.ui.Button):
    def __init__(self, label: str, week_count: int, deadline: datetime):
        self.week_count = week_count
        self.deadline = deadline
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        if self.week_count == 2:
            week_1_label = _target_week_label(1)
            week_2_label = _target_week_label(2)
            embed = discord.Embed(
                title=f"⏳ Choose {week_2_label} deadline",
                description=(
                    f"✅ {week_1_label} deadline: **{self.deadline.strftime('%A %d/%m at %H:%M')}**\n"
                    "Choose when availability collection closes for the week after. 📅"
                ),
                color=discord.Color.orange(),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=SecondWeekDeadlineView(self.deadline),
            )
            return

        await _start_planning(
            interaction=interaction,
            week_count=1,
            week_deadlines={1: self.deadline},
        )


class SecondWeekDeadlineButton(discord.ui.Button):
    def __init__(self, day: datetime, first_week_deadline: datetime):
        self.day = day
        self.first_week_deadline = first_week_deadline

        label = day.strftime("%a %d/%m")
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        second_week_deadline = datetime.combine(self.day.date(), time(hour=23, minute=59))
        await _start_planning(
            interaction=interaction,
            week_count=2,
            week_deadlines={
                1: self.first_week_deadline,
                2: second_week_deadline,
            },
        )


class SecondWeekDeadlineView(discord.ui.View):
    def __init__(self, first_week_deadline: datetime):
        super().__init__(timeout=300)

        for day in get_deadline_days_before_target_week(2):
            self.add_item(SecondWeekDeadlineButton(day, first_week_deadline))


async def _start_planning(
    interaction: discord.Interaction,
    week_count: int,
    week_deadlines: dict[int, datetime],
) -> None:
    deadline = max(week_deadlines.values())
    set_planning_deadline(deadline, week_count, week_deadlines)

    log.info(
        "Planning started by user_id=%s with final_deadline=%s week_count=%s",
        interaction.user.id,
        deadline.isoformat(),
        week_count,
    )

    deadlines_text = "\n".join(
        f"{_target_week_label(week_index)}: **{week_deadline.strftime('%A %d/%m at %H:%M')}**"
        for week_index, week_deadline in sorted(week_deadlines.items())
    )
    embed = discord.Embed(
        title="✅ Planning started",
        description=(
            f"Availability collection is now open. 🎲\n"
            f"{deadlines_text}"
        ),
        color=discord.Color.green(),
    )

    await interaction.response.edit_message(embed=embed, view=None)

    if interaction.channel is not None:
        await interaction.channel.send(
            embed=build_public_availability_embed(deadline),
            view=PublicAvailabilityView(),
        )

    await _dm_registered_players(interaction.client, deadline)


async def _dm_registered_players(
    client: discord.Client,
    deadline: datetime,
) -> None:
    for player in get_registered_players():
        user_id = player["user_id"]
        try:
            user = client.get_user(user_id) or await client.fetch_user(user_id)
            await user.send(
                embed=build_player_availability_invite_embed(deadline),
                view=PublicAvailabilityView(),
            )
        except Exception:
            log.exception("Failed to send planning invite to user_id=%s", user_id)


class PlanningWeekCountView(discord.ui.View):
    def __init__(self, deadline: datetime):
        super().__init__(timeout=300)
        self.add_item(WeekCountButton("Next week", 1, deadline))
        self.add_item(WeekCountButton("Next week + week after", 2, deadline))


def _target_week_label(week_index: int) -> str:
    week_start = get_target_week_start(week_index=week_index)
    return get_target_week_label(week_start, week_index).lower()


class PlanningDeadlineView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

        for day in get_upcoming_week_days():
            self.add_item(DeadlineButton(day))
