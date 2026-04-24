from datetime import datetime

import discord

from bot.storage.profiles import get_profile
from bot.storage.planning import (
    get_planning_deadline,
    get_planning_started_at,
    get_user_availabilities,
    get_user_availability_note,
    is_planning_open,
    save_user_availability,
    save_user_availability_note,
)
from bot.ui.register_view import RegisterView
from bot.utils.planning import get_availability_slots


STATUS_LABELS = {
    "available": "Available",
    "doubtful": "Doubtful",
    "unavailable": "Unavailable",
}
STATUS_EMOJIS = {
    None: "⬜",
    "available": "🟩",
    "doubtful": "🟦",
    "unavailable": "🟥",
}
STATUS_STYLES = {
    None: discord.ButtonStyle.secondary,
    "available": discord.ButtonStyle.success,
    "doubtful": discord.ButtonStyle.primary,
    "unavailable": discord.ButtonStyle.danger,
}
NEXT_STATUS = {
    None: "available",
    "available": "doubtful",
    "doubtful": "unavailable",
    "unavailable": None,
}
LEGEND = "⬜ Unset  🟩 Available  🟨 Doubtful  🟥 Unavailable"


def build_public_availability_embed(deadline: datetime) -> discord.Embed:
    embed = discord.Embed(
        title="Planning is open",
        description=(
            "Enter your availability for the next session.\n"
            f"{LEGEND}\n"
            f"Deadline: **{deadline.strftime('%A %d/%m at %H:%M')}**"
        ),
        color=discord.Color.green(),
    )
    return embed


class PublicAvailabilityView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enter availability",
        style=discord.ButtonStyle.primary,
        custom_id="planning:enter_availability",
    )
    async def enter_availability(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        deadline = get_planning_deadline()
        if deadline is None or not is_planning_open():
            await interaction.response.send_message(
                "Planning is not open right now.",
                ephemeral=True,
            )
            return

        user_id = interaction.user.id
        if get_profile(user_id) is None:
            embed = discord.Embed(
                title="You are not registered yet",
                description="Create your DnD profile before entering availability.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(
                embed=embed,
                view=RegisterView(),
                ephemeral=True,
            )
            return

        started_at = get_planning_started_at()
        view = AvailabilityView(
            user_id=user_id,
            slots=get_availability_slots(started_at),
            statuses=get_user_availabilities(user_id),
            note=get_user_availability_note(user_id),
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True,
        )


class AvailabilityView(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        slots: list[tuple[str, str]],
        statuses: dict[str, str],
        note: str | None,
    ):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.slots = slots
        self.statuses = statuses
        self.note = note

        for index, (slot_key, label) in enumerate(slots):
            row = 0 if index < 5 else 1
            self.add_item(AvailabilitySlotButton(slot_key, label, row))

        self.add_item(EditNoteButton())
        self.refresh_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            if is_planning_open():
                return True

            await interaction.response.send_message(
                "Planning is closed. Availability changes are no longer accepted.",
                ephemeral=True,
            )
            return False

        await interaction.response.send_message(
            "This availability form belongs to another player.",
            ephemeral=True,
        )
        return False

    def refresh_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, AvailabilitySlotButton):
                status = self.statuses.get(item.slot_key)
                item.style = STATUS_STYLES[status]
                item.label = f"{STATUS_EMOJIS[status]} {item.slot_label}"

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Your availability",
            description="Click a time slot to cycle through each status.",
            color=discord.Color.blurple(),
        )

        for status, label in STATUS_LABELS.items():
            slots = [
                slot_label
                for slot_key, slot_label in self.slots
                if self.statuses.get(slot_key) == status
            ]
            embed.add_field(
                name=f"{STATUS_EMOJIS[status]} {label}",
                value="\n".join(slots) or "-",
                inline=True,
            )

        embed.add_field(name="Note", value=self.note or "-", inline=False)
        return embed


class AvailabilitySlotButton(discord.ui.Button):
    def __init__(self, slot_key: str, label: str, row: int):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id=f"planning:slot:{slot_key}",
        )
        self.slot_key = slot_key
        self.slot_label = label

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, AvailabilityView):
            return

        next_status = NEXT_STATUS[view.statuses.get(self.slot_key)]
        if next_status is None:
            view.statuses.pop(self.slot_key, None)
        else:
            view.statuses[self.slot_key] = next_status

        if not save_user_availability(view.user_id, self.slot_key, next_status):
            await interaction.response.send_message(
                "Planning is closed. Availability changes are no longer accepted.",
                ephemeral=True,
            )
            return

        view.refresh_buttons()

        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class EditNoteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Add note",
            style=discord.ButtonStyle.secondary,
            row=2,
            custom_id="planning:edit_note",
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, AvailabilityView):
            return

        await interaction.response.send_modal(AvailabilityNoteModal(view))


class AvailabilityNoteModal(discord.ui.Modal):
    def __init__(self, availability_view: AvailabilityView):
        super().__init__(title="Availability note")
        self.availability_view = availability_view
        self.note_input = discord.ui.TextInput(
            label="Note",
            style=discord.TextStyle.paragraph,
            default=availability_view.note or "",
            required=False,
            max_length=500,
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.availability_view.user_id:
            await interaction.response.send_message(
                "This availability form belongs to another player.",
                ephemeral=True,
            )
            return

        if not is_planning_open():
            await interaction.response.send_message(
                "Planning is closed. Availability changes are no longer accepted.",
                ephemeral=True,
            )
            return

        note = str(self.note_input).strip()
        if not save_user_availability_note(self.availability_view.user_id, note):
            await interaction.response.send_message(
                "Planning is closed. Availability changes are no longer accepted.",
                ephemeral=True,
            )
            return

        self.availability_view.note = note or None

        await interaction.response.edit_message(
            embed=self.availability_view.build_embed(),
            view=self.availability_view,
        )
