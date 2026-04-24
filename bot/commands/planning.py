import discord

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