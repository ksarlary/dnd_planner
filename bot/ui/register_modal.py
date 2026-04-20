import discord

from bot.storage.profiles import save_profile


class RegisterModal(discord.ui.Modal, title="Register your character"):
    nickname = discord.ui.TextInput(
        label="Nickname",
        placeholder="Enter your nickname",
        max_length=50,
    )

    race = discord.ui.TextInput(
        label="Race",
        placeholder="Elf, Human, Tiefling...",
        max_length=50,
    )

    player_class = discord.ui.TextInput(
        label="Class",
        placeholder="Wizard, Rogue, Cleric...",
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        save_profile(
            user_id=interaction.user.id,
            nickname=str(self.nickname),
            race=str(self.race),
            player_class=str(self.player_class),
        )

        embed = discord.Embed(
            title="Profile created",
            color=discord.Color.green()
        )
        embed.add_field(name="Nickname", value=str(self.nickname), inline=False)
        embed.add_field(name="Race", value=str(self.race), inline=False)
        embed.add_field(name="Class", value=str(self.player_class), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)