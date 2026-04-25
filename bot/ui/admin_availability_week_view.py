import discord

from bot.storage.planning import get_planning_target_weeks
from bot.ui.planning_selection_view import PlanningSelectionView
from bot.utils.availability_summary import (
    build_week_availability_summary_embed,
    get_week_suggested_dates,
)


class AdminAvailabilityWeekView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

        for target_week in get_planning_target_weeks():
            self.add_item(
                AdminAvailabilityWeekButton(
                    week_index=target_week["week_index"],
                    label=target_week["week_label"],
                )
            )


class AdminAvailabilityWeekButton(discord.ui.Button):
    def __init__(self, week_index: int, label: str):
        self.week_index = week_index
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        suggestions = get_week_suggested_dates(self.week_index)
        await interaction.response.edit_message(
            embed=build_week_availability_summary_embed(self.week_index),
            view=PlanningSelectionView(suggestions, self.week_index),
        )
