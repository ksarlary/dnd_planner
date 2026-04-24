import logging
from datetime import datetime, time

import discord

from bot.storage.planning import set_planning_deadline
from bot.ui.availability_view import PublicAvailabilityView, build_public_availability_embed
from bot.utils.planning import get_upcoming_week_days

log = logging.getLogger("discord-bot")


class DeadlineButton(discord.ui.Button):
    def __init__(self, day: datetime):
        self.day = day

        label = day.strftime("%a %d/%m")
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        deadline = datetime.combine(self.day.date(), time(hour=23, minute=59))
        set_planning_deadline(deadline)

        log.info(
            "Planning deadline set by user_id=%s to %s",
            interaction.user.id,
            deadline.isoformat(),
        )

        embed = discord.Embed(
            title="Planning started",
            description=(
                f"Availability collection is now open.\n"
                f"Deadline: **{deadline.strftime('%A %d/%m at %H:%M')}**"
            ),
            color=discord.Color.green(),
        )

        await interaction.response.edit_message(embed=embed, view=None)

        if interaction.channel is not None:
            await interaction.channel.send(
                embed=build_public_availability_embed(deadline),
                view=PublicAvailabilityView(),
            )


class PlanningDeadlineView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

        for day in get_upcoming_week_days():
            self.add_item(DeadlineButton(day))
