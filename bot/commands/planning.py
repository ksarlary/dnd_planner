import discord

from bot.storage.planning import get_planning_started_at
from bot.ui.admin_planning_view import AdminPlanningView, build_admin_availability_embed
from bot.ui.planning_deadline_view import PlanningDeadlineView
from bot.utils.checks import is_admin


def setup_planning_commands(bot) -> None:
    @bot.tree.command(
        name="start_planning",
        description="Start availability collection and choose the deadline"
    )
    @is_admin()
    async def start_planning(interaction: discord.Interaction):
        embed = discord.Embed(
            title="Start planning",
            description="Choose the day when availability collection will close at 23:59.",
            color=discord.Color.orange(),
        )

        await interaction.response.send_message(
            embed=embed,
            view=PlanningDeadlineView(),
            ephemeral=True,
        )

    @bot.tree.command(
        name="availabilities",
        description="Display availabilities and plan a session"
    )
    @is_admin()
    async def availabilities(interaction: discord.Interaction):
        started_at = get_planning_started_at()
        if started_at is None:
            await interaction.response.send_message(
                "No planning has been started yet.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=build_admin_availability_embed(started_at),
            view=AdminPlanningView(interaction.user.id, started_at),
            ephemeral=True,
        )
