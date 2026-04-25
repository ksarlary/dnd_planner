import discord

from bot.storage.planning import get_planning_target_weeks
from bot.ui.admin_availability_week_view import AdminAvailabilityWeekView
from bot.ui.planning_deadline_view import PlanningDeadlineView
from bot.ui.planning_selection_view import PlanningSelectionView
from bot.utils.availability_summary import (
    build_week_availability_summary_embed,
    get_week_suggested_dates,
)
from bot.utils.checks import is_admin
from bot.utils.planning import get_target_week_label, get_target_week_start


def setup_planning_commands(bot) -> None:
    @bot.tree.command(
        name="start_planning",
        description="Start availability collection and choose the deadline"
    )
    @is_admin()
    async def start_planning(interaction: discord.Interaction):
        week_start = get_target_week_start(week_index=1)
        week_label = get_target_week_label(week_start, 1).lower()
        embed = discord.Embed(
            title="🗓️ Start planning",
            description=f"Choose the day when availability collection will close for {week_label} at 23:59. ⏳",
            color=discord.Color.orange(),
        )

        await interaction.response.send_message(
            embed=embed,
            view=PlanningDeadlineView(),
            ephemeral=True,
        )

    @bot.tree.command(
        name="availabilities",
        description="Show the current planning availability summary"
    )
    @is_admin()
    async def availabilities(interaction: discord.Interaction):
        target_weeks = get_planning_target_weeks()
        if len(target_weeks) > 1:
            embed = discord.Embed(
                title="🗓️ Choose a planning week",
                description="Pick the week you want to display and planify. 📜",
                color=discord.Color.blurple(),
            )
            await interaction.response.send_message(
                embed=embed,
                view=AdminAvailabilityWeekView(),
                ephemeral=True,
            )
            return

        week_index = target_weeks[0]["week_index"] if target_weeks else 1
        suggestions = get_week_suggested_dates(week_index)
        await interaction.response.send_message(
            embed=build_week_availability_summary_embed(week_index),
            view=PlanningSelectionView(suggestions, week_index),
            ephemeral=True,
        )
