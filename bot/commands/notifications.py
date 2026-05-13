import discord

from bot.storage.notifications import (
    get_notification_settings,
    update_notification_setting,
)


SETTING_LABELS = {
    "dms_enabled": "DMs from the bot",
    "availability_reminders_enabled": "Missing availability reminders",
    "session_reminders_enabled": "Upcoming session reminders",
    "planned_session_messages_enabled": "Planned session messages",
}


def setup_notification_commands(bot) -> None:
    @bot.tree.command(
        name="notifications",
        description="Configure bot DMs and reminder notifications",
    )
    async def notifications(interaction: discord.Interaction):
        settings = get_notification_settings(interaction.user.id)
        await interaction.response.send_message(
            embed=build_notifications_embed(settings),
            view=NotificationsView(interaction.user.id, settings),
            ephemeral=True,
        )


class NotificationsView(discord.ui.View):
    def __init__(self, user_id: int, settings: dict):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.settings = settings
        self._add_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

        await interaction.response.send_message(
            "This notification panel belongs to another player.",
            ephemeral=True,
        )
        return False

    def _add_buttons(self) -> None:
        self.clear_items()
        self.add_item(NotificationToggleButton("dms_enabled", row=0))
        self.add_item(NotificationToggleButton("availability_reminders_enabled", row=1))
        self.add_item(NotificationToggleButton("session_reminders_enabled", row=1))
        self.add_item(NotificationToggleButton("planned_session_messages_enabled", row=2))

        for item in self.children:
            if isinstance(item, NotificationToggleButton):
                item.refresh(self.settings)

    def refresh(self, settings: dict) -> None:
        self.settings = settings
        self._add_buttons()


class NotificationToggleButton(discord.ui.Button):
    def __init__(self, setting_key: str, row: int):
        self.setting_key = setting_key
        super().__init__(row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, NotificationsView):
            return

        settings = update_notification_setting(
            view.user_id,
            self.setting_key,
            not view.settings[self.setting_key],
        )
        view.refresh(settings)

        await interaction.response.edit_message(
            embed=build_notifications_embed(settings),
            view=view,
        )

    def refresh(self, settings: dict) -> None:
        enabled = settings[self.setting_key]
        self.label = f"{SETTING_LABELS[self.setting_key]}: {'ON' if enabled else 'OFF'}"
        self.style = (
            discord.ButtonStyle.success
            if enabled
            else discord.ButtonStyle.secondary
        )

        self.disabled = (
            self.setting_key != "dms_enabled"
            and not settings["dms_enabled"]
        )


def build_notifications_embed(settings: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🔔 Notification settings",
        description=(
            "Choose which bot DMs you want to receive.\n"
            "If DMs are disabled, all reminder and announcement options are turned off."
        ),
        color=discord.Color.blurple(),
    )

    for key, label in SETTING_LABELS.items():
        embed.add_field(
            name=label,
            value="✅ Enabled" if settings[key] else "⬜ Disabled",
            inline=False,
        )

    return embed
