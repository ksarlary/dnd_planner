import discord

from bot.ui.register_modal import RegisterModal


class ProfileView(discord.ui.View):
    def __init__(self, profile_data: dict[str, str]):
        super().__init__(timeout=300)
        self.profile_data = profile_data

    @discord.ui.button(label="Edit profile", style=discord.ButtonStyle.primary)
    async def edit_profile_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(RegisterModal(self.profile_data))
