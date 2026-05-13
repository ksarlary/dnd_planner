import discord

from bot.storage.planning import (
    get_all_availabilities,
    get_all_availability_notes,
    get_last_recap_player,
    get_registered_players,
    get_selected_planning_slot,
    set_planning_recap_player,
    set_selected_planning_slot,
)
from bot.utils.planning import get_availability_slots


STATUS_EMOJIS = {
    None: "⬜",
    "available": "🟩",
    "doubtful": "🟦",
    "unavailable": "🟥",
}
STATUS_LABELS = {
    "available": "Available",
    "doubtful": "Doubtful",
    "unavailable": "Unavailable",
    None: "Missing",
}
RECAP_ORDER = ["Sonia", "Shin", "Atouf", "Balico"]


def _clip(value: str, limit: int = 1024) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _format_players(players: list[str]) -> str:
    return ", ".join(players) if players else "-"


def _sort_players_for_recap(players: list[dict]) -> list[dict]:
    order_by_name = {
        nickname.lower(): index
        for index, nickname in enumerate(RECAP_ORDER)
    }

    return sorted(
        players,
        key=lambda player: (
            order_by_name.get(player["nickname"].lower(), len(RECAP_ORDER)),
            player["nickname"].lower(),
        ),
    )


def build_slot_suggestions(
    slots: list[tuple[str, str]],
    players: list[dict],
    availabilities: dict[int, dict[str, str]],
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    sure_dates = []
    probable_dates = []

    if not players:
        return sure_dates, probable_dates

    for slot_key, slot_label in slots:
        statuses = [
            availabilities.get(player["user_id"], {}).get(slot_key)
            for player in players
        ]

        if all(status == "available" for status in statuses):
            sure_dates.append((slot_key, slot_label, "Everyone available"))
            continue

        if all(status in {"available", "doubtful"} for status in statuses):
            doubtful_players = [
                player["nickname"]
                for player, status in zip(players, statuses)
                if status == "doubtful"
            ]
            if doubtful_players:
                reason = f"Doubtful: {_format_players(doubtful_players)}"
                probable_dates.append((slot_key, slot_label, reason))

    return sure_dates, probable_dates


def build_admin_availability_embed(started_at) -> discord.Embed:
    slots = get_availability_slots(started_at)
    players = get_registered_players()
    availabilities = get_all_availabilities()
    notes = get_all_availability_notes()
    selected_slot = get_selected_planning_slot()
    last_recap = get_last_recap_player(
        exclude_slot_label=selected_slot["slot_label"] if selected_slot else None,
    )
    sure_dates, probable_dates = build_slot_suggestions(slots, players, availabilities)

    embed = discord.Embed(
        title="Availabilities",
        description=(
            "Review player availability, choose a suggested date, or use the "
            "conflicted date menu to override the table after the deadline."
        ),
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="📜 Recap order",
        value=" -> ".join(RECAP_ORDER),
        inline=False,
    )
    embed.add_field(
        name="Last recap",
        value=last_recap["nickname"] if last_recap else "-",
        inline=False,
    )

    if selected_slot:
        mode = "conflicted override" if selected_slot["manual_override"] else "suggested date"
        recap = selected_slot["recap_nickname"] or "not chosen yet"
        embed.add_field(
            name="🎲 Planned session",
            value=(
                f"**{selected_slot['slot_label']}** ({mode})\n"
                f"Recap: **{recap}**"
            ),
            inline=False,
        )

    if sure_dates:
        embed.add_field(
            name="✅ Sure suggestions",
            value=_clip("\n".join(label for _, label, _ in sure_dates)),
            inline=False,
        )
    else:
        embed.add_field(name="✅ Sure suggestions", value="-", inline=False)

    if probable_dates:
        embed.add_field(
            name="🟦 Probable suggestions",
            value=_clip("\n".join(f"{label} ({reason})" for _, label, reason in probable_dates)),
            inline=False,
        )
    else:
        embed.add_field(name="🟦 Probable suggestions", value="-", inline=False)

    for slot_key, slot_label in slots:
        grouped = {"available": [], "doubtful": [], "unavailable": [], None: []}
        for player in players:
            status = availabilities.get(player["user_id"], {}).get(slot_key)
            grouped[status].append(player["nickname"])

        lines = [
            f"{STATUS_EMOJIS[status]} {STATUS_LABELS[status]}: {_format_players(names)}"
            for status, names in grouped.items()
        ]
        embed.add_field(name=slot_label, value=_clip("\n".join(lines)), inline=False)

    if notes:
        note_lines = []
        players_by_id = {player["user_id"]: player for player in players}
        for user_id, note in notes.items():
            nickname = players_by_id.get(user_id, {}).get("nickname", str(user_id))
            note_lines.append(f"**{nickname}**: {note}")
        embed.add_field(name="Notes", value=_clip("\n".join(note_lines)), inline=False)

    return embed


class AdminPlanningView(discord.ui.View):
    def __init__(self, admin_id: int, started_at):
        super().__init__(timeout=900)
        self.admin_id = admin_id
        self.started_at = started_at

        slots = get_availability_slots(started_at)
        players = get_registered_players()
        availabilities = get_all_availabilities()
        sure_dates, probable_dates = build_slot_suggestions(slots, players, availabilities)
        suggestions = [*sure_dates, *probable_dates]

        if suggestions:
            self.add_item(SuggestedDateSelect(suggestions))

        self.add_item(ConflictedDateSelect(slots))

        if players:
            self.add_item(RecapPlayerSelect(_sort_players_for_recap(players)))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.admin_id:
            return True

        await interaction.response.send_message(
            "Only the admin who opened this panel can plan the session from it.",
            ephemeral=True,
        )
        return False

    async def select_slot(
        self,
        interaction: discord.Interaction,
        slot_key: str,
        slot_label: str,
        manual_override: bool,
    ) -> None:
        set_selected_planning_slot(slot_key, slot_label, manual_override)
        selected_slot = get_selected_planning_slot()
        recap = selected_slot["recap_nickname"] if selected_slot else None

        await interaction.response.edit_message(
            embed=build_admin_availability_embed(self.started_at),
            view=AdminPlanningView(self.admin_id, self.started_at),
        )

        if interaction.channel is not None:
            if manual_override:
                message = (
                    f"⚠️ Session planned on **{slot_label}** as a conflicted override. "
                    "Check your bags, schedules, and dramatic monologues."
                )
            else:
                message = f"🎲 Session planned on **{slot_label}**. Prepare the dice."

            if recap:
                message += f"\n📜 Recap: **{recap}**."

            await interaction.channel.send(message)

    async def select_recap_player(
        self,
        interaction: discord.Interaction,
        user_id: int,
        nickname: str,
    ) -> None:
        if not set_planning_recap_player(user_id, nickname):
            await interaction.response.send_message(
                "Choose a session date first, then assign recap duty.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            embed=build_admin_availability_embed(self.started_at),
            view=AdminPlanningView(self.admin_id, self.started_at),
        )

        if interaction.channel is not None:
            await interaction.channel.send(
                f"📜 Recap duty updated: **{nickname}** will handle the previous-session recap."
            )


class SuggestedDateSelect(discord.ui.Select):
    def __init__(self, suggestions: list[tuple[str, str, str]]):
        options = [
            discord.SelectOption(
                label=label,
                value=slot_key,
                description=reason[:100],
                emoji="✅" if reason == "Everyone available" else "🟦",
            )
            for slot_key, label, reason in suggestions[:25]
        ]
        self.options_by_key = {
            slot_key: label
            for slot_key, label, _ in suggestions
        }

        super().__init__(
            placeholder="Choose a suggested date",
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, AdminPlanningView):
            return

        slot_key = self.values[0]
        await view.select_slot(
            interaction,
            slot_key,
            self.options_by_key[slot_key],
            manual_override=False,
        )


class ConflictedDateSelect(discord.ui.Select):
    def __init__(self, slots: list[tuple[str, str]]):
        options = [
            discord.SelectOption(
                label=label,
                value=slot_key,
                description="Manual conflicted date override",
                emoji="⚠️",
            )
            for slot_key, label in slots[:25]
        ]
        self.options_by_key = {slot_key: label for slot_key, label in slots}

        super().__init__(
            placeholder="Choose any conflicted date",
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, AdminPlanningView):
            return

        slot_key = self.values[0]
        await view.select_slot(
            interaction,
            slot_key,
            self.options_by_key[slot_key],
            manual_override=True,
        )


class RecapPlayerSelect(discord.ui.Select):
    def __init__(self, players: list[dict]):
        options = [
            discord.SelectOption(
                label=player["nickname"],
                value=str(player["user_id"]),
                description=f"{player['race']} {player['class']}"[:100],
                emoji="📜",
            )
            for player in players[:25]
        ]
        self.players_by_id = {
            str(player["user_id"]): player
            for player in players
        }

        super().__init__(
            placeholder="Choose who does the recap",
            options=options,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, AdminPlanningView):
            return

        selected_id = self.values[0]
        player = self.players_by_id[selected_id]
        await view.select_recap_player(
            interaction,
            int(selected_id),
            player["nickname"],
        )
