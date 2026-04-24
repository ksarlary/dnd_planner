import discord
from discord import app_commands

from bot.storage.profiles import get_profile
from bot.ui.profile_view import ProfileView
from bot.ui.register_view import RegisterView


def setup_profile_commands(bot) -> None:
    @bot.tree.command(name="profile", description="Show your DnD profile or register if you don't have one yet")
    async def profile(interaction: discord.Interaction):
        profile_data = get_profile(interaction.user.id)

        if not profile_data:
            embed = discord.Embed(
                title="You are not registered yet",
                description="Click the button below to create your DnD profile.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(
                embed=embed,
                view=RegisterView(),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Profile",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Nickname", value=profile_data["nickname"], inline=False)
        embed.add_field(name="Race", value=profile_data["race"], inline=False)
        embed.add_field(name="Class", value=profile_data["class"], inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=ProfileView(profile_data),
            ephemeral=True,
        )
