from datetime import datetime

import discord

from bot.storage.profiles import get_profile
from bot.storage.planning import (
    get_planning_deadline,
    get_planning_started_at,
    get_planning_week,
    get_planning_target_weeks,
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
LEGEND = "⬜ Unset  🟩 Available  🟦 Doubtful  🟥 Unavailable"


def build_public_availability_embed(deadline: datetime) -> discord.Embed:
    deadlines_text = _format_target_week_deadlines(deadline)
    embed = discord.Embed(
        title="🗓️ Planning is open",
        description=(
            "Enter your availability for the target planning week or weeks. 🎲\n"
            f"{LEGEND}\n"
            f"{deadlines_text}"
        ),
        color=discord.Color.green(),
    )
    return embed


def build_player_availability_invite_embed(deadline: datetime) -> discord.Embed:
    deadlines_text = _format_target_week_deadlines(deadline)
    embed = discord.Embed(
        title="🧭 Your party needs your availability",
        description=(
            "Planning is open. Choose the dates where you can join for each target week. 🎲\n"
            f"{LEGEND}\n"
            f"{deadlines_text}"
        ),
        color=discord.Color.green(),
    )
    return embed


def build_missing_availability_reminder_embed(
    deadline: datetime,
    missing_labels: list[str],
) -> discord.Embed:
    missing_text = "\n".join(missing_labels[:10])
    if len(missing_labels) > 10:
        missing_text += f"\n...and {len(missing_labels) - 10} more"

    embed = discord.Embed(
        title="⏰ Tiny scheduling nudge",
        description=(
            "The calendar still has mysterious blank spots with your name on them.\n"
            "Please fill the missing availabilities before the DM starts preparing consequences.\n"
            f"Deadline: **{deadline.strftime('%A %d/%m at %H:%M')}**"
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(
        name="🕳️ Missing",
        value=missing_text or "No missing slots.",
        inline=False,
    )
    return embed


def _format_target_week_deadlines(fallback_deadline: datetime) -> str:
    target_weeks = get_planning_target_weeks()
    if not target_weeks:
        return f"Deadline: **{fallback_deadline.strftime('%A %d/%m at %H:%M')}**"

    return "\n".join(
        f"{target_week['week_label']} deadline: **{target_week['deadline'].strftime('%A %d/%m at %H:%M')}**"
        for target_week in target_weeks
        if target_week["deadline"] is not None
    )


def build_sessions_planned_embed(
    session_labels: list[str],
    taunt: str | None = None,
    recap_nickname: str | None = None,
    session_recaps: list[tuple[str, str]] | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title="🎲 Sessions planned",
        description=(
            "The party calendar has spoken. Pack snacks, sharpen pencils, "
            "and prepare your finest questionable decisions."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(
        name="📅 Incoming sessions",
        value="\n".join(f"- {label}" for label in session_labels),
        inline=False,
    )
    if session_recaps:
        embed.add_field(
            name="📜 Previous session recap",
            value="\n".join(
                f"**{label}**: {nickname}"
                for label, nickname in session_recaps
            ),
            inline=False,
        )
    elif recap_nickname:
        embed.add_field(
            name="📜 Previous session recap",
            value=f"{recap_nickname} is on recap duty.",
            inline=False,
        )
    if taunt:
        embed.add_field(name="🪶 Calendar blame", value=taunt, inline=False)
    return embed


def build_no_session_planned_embed(
    week_label: str,
    taunt: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title="🛌 No session planned",
        description=(
            f"No DnD session is planned for **{week_label.lower()}**.\n"
            "The calendar takes a dramatic pause. Use it wisely."
        ),
        color=discord.Color.orange(),
    )
    if taunt:
        embed.add_field(name="🪶 Calendar blame", value=taunt, inline=False)
    return embed


def build_session_day_before_reminder_embed(
    session_label: str,
    recap_nickname: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title="⏰ Session tomorrow",
        description=(
            "Your next DnD session is tomorrow. The dice are stretching. "
            "The DM is smiling. That is probably fine."
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(name="📅 When", value=session_label, inline=False)
    if recap_nickname:
        embed.add_field(
            name="📜 Recap",
            value=f"{recap_nickname} is doing the previous session recap.",
            inline=False,
        )
    return embed


def _use_ephemeral(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None


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
                ephemeral=_use_ephemeral(interaction),
            )
            return

        user_id = interaction.user.id
        if get_profile(user_id) is None:
            embed = discord.Embed(
                title="🧾 You are not registered yet",
                description="Create your DnD profile before entering availability. ✍️",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(
                embed=embed,
                view=RegisterView(),
                ephemeral=_use_ephemeral(interaction),
            )
            return

        started_at = get_planning_started_at()
        target_weeks = get_planning_target_weeks()
        if len(target_weeks) > 1:
            view = AvailabilityWeekSelectionView(
                user_id=user_id,
                target_weeks=target_weeks,
            )
            await interaction.response.send_message(
                embed=view.build_embed(),
                view=view,
                ephemeral=_use_ephemeral(interaction),
            )
            return

        week_index = target_weeks[0]["week_index"] if target_weeks else 1
        view = build_availability_view_for_week(user_id, started_at, week_index)

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=_use_ephemeral(interaction),
        )


def build_availability_view_for_week(
    user_id: int,
    started_at: datetime | None,
    week_index: int,
) -> "AvailabilityView":
    return AvailabilityView(
        user_id=user_id,
        week_index=week_index,
        slots=get_availability_slots(started_at, week_index),
        statuses=get_user_availabilities(user_id),
        note=get_user_availability_note(user_id, week_index),
    )


class AvailabilityWeekSelectionView(discord.ui.View):
    def __init__(self, user_id: int, target_weeks: list[dict]):
        super().__init__(timeout=300)
        self.user_id = user_id

        for target_week in target_weeks:
            self.add_item(
                AvailabilityWeekButton(
                    user_id=user_id,
                    week_index=target_week["week_index"],
                    label=target_week["week_label"],
                )
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True

        await interaction.response.send_message(
            "This availability form belongs to another player.",
            ephemeral=_use_ephemeral(interaction),
        )
        return False

    def build_embed(self) -> discord.Embed:
        return discord.Embed(
            title="🗓️ Choose a week",
            description="Pick the week you want to complete. 📌",
            color=discord.Color.blurple(),
        )


class AvailabilityWeekButton(discord.ui.Button):
    def __init__(self, user_id: int, week_index: int, label: str):
        self.user_id = user_id
        self.week_index = week_index
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        if not is_planning_open(week_index=self.week_index):
            await interaction.response.send_message(
                "Planning is closed for this week. Availability changes are no longer accepted.",
                ephemeral=_use_ephemeral(interaction),
            )
            return

        started_at = get_planning_started_at()
        view = build_availability_view_for_week(
            self.user_id,
            started_at,
            self.week_index,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class AvailabilityView(discord.ui.View):
    def __init__(
        self,
        user_id: int,
        week_index: int,
        slots: list[tuple[str, str]],
        statuses: dict[str, str],
        note: str | None,
    ):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.week_index = week_index
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
            if is_planning_open(week_index=self.week_index):
                return True

            await interaction.response.send_message(
                "Planning is closed for this week. Availability changes are no longer accepted.",
                ephemeral=_use_ephemeral(interaction),
            )
            return False

        await interaction.response.send_message(
            "This availability form belongs to another player.",
            ephemeral=_use_ephemeral(interaction),
        )
        return False

    def refresh_buttons(self) -> None:
        for item in self.children:
            if isinstance(item, AvailabilitySlotButton):
                status = self.statuses.get(item.slot_key)
                item.style = STATUS_STYLES[status]
                item.label = f"{STATUS_EMOJIS[status]} {item.slot_label}"

    def build_embed(self) -> discord.Embed:
        target_week = get_planning_week(self.week_index)
        deadline = target_week["deadline"] if target_week else None
        week_label = target_week["week_label"] if target_week else f"week {self.week_index}"
        description = "Click a time slot to cycle through each status."
        if deadline is not None:
            description += f"\nDeadline: **{deadline.strftime('%A %d/%m at %H:%M')}**"

        embed = discord.Embed(
            title=f"🧭 Your availability - {week_label.lower()}",
            description=description,
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

        embed.add_field(name="📝 Note", value=self.note or "-", inline=False)
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
                ephemeral=_use_ephemeral(interaction),
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
                ephemeral=_use_ephemeral(interaction),
            )
            return

        if not is_planning_open(week_index=self.availability_view.week_index):
            await interaction.response.send_message(
                "Planning is closed. Availability changes are no longer accepted.",
                ephemeral=_use_ephemeral(interaction),
            )
            return

        note = str(self.note_input).strip()
        if not save_user_availability_note(
            self.availability_view.user_id,
            note,
            self.availability_view.week_index,
        ):
            await interaction.response.send_message(
                "Planning is closed. Availability changes are no longer accepted.",
                ephemeral=_use_ephemeral(interaction),
            )
            return

        self.availability_view.note = note or None

        await interaction.response.edit_message(
            embed=self.availability_view.build_embed(),
            view=self.availability_view,
        )
