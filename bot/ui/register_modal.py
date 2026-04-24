import discord

from bot.storage.profiles import save_profile


class RegisterModal(discord.ui.Modal):
    def __init__(self, profile_data: dict[str, str] | None = None):
        super().__init__(
            title="Edit your character" if profile_data else "Register your character"
        )
        self.is_edit = profile_data is not None

        self.nickname = discord.ui.TextInput(
            label="Nickname",
            placeholder="Enter your nickname",
            default=profile_data["nickname"] if profile_data else None,
            max_length=50,
        )
        self.race = discord.ui.TextInput(
            label="Race",
            placeholder="Elf, Human, Tiefling...",
            default=profile_data["race"] if profile_data else None,
            max_length=50,
        )
        self.player_class = discord.ui.TextInput(
            label="Class",
            placeholder="Wizard, Rogue, Cleric...",
            default=profile_data["class"] if profile_data else None,
            max_length=50,
        )

        self.add_item(self.nickname)
        self.add_item(self.race)
        self.add_item(self.player_class)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        save_profile(
            user_id=interaction.user.id,
            nickname=str(self.nickname),
            race=str(self.race),
            player_class=str(self.player_class),
        )

        embed = discord.Embed(
            title="Profile updated" if self.is_edit else "Profile created",
            color=discord.Color.green()
        )
        embed.add_field(name="Nickname", value=str(self.nickname), inline=False)
        embed.add_field(name="Race", value=str(self.race), inline=False)
        embed.add_field(name="Class", value=str(self.player_class), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
