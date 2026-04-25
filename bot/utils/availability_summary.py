from dataclasses import dataclass, field
from datetime import datetime

import discord

from bot.storage.planning import (
    get_planning_deadline,
    get_planning_started_at,
    get_planning_summary_rows,
    get_planning_week,
    get_selected_planning_slots,
)
from bot.utils.planning import get_availability_slot_details, get_availability_slots


STATUS_EMOJIS = {
    "available": "🟩",
    "doubtful": "🟨",
    "unavailable": "🟥",
    "missing": "⬜",
}


@dataclass
class PlayerAvailability:
    nickname: str
    note: str | None = None
    statuses: dict[str, str] = field(default_factory=dict)


@dataclass
class SuggestedDate:
    slot_key: str
    label: str
    session_datetime: datetime
    kind: str
    doubtful_players: list[str] = field(default_factory=list)


def build_availability_summary_embed() -> discord.Embed:
    return build_week_availability_summary_embed(1)


def build_week_availability_summary_embed(week_index: int) -> discord.Embed:
    target_week = get_planning_week(week_index)
    deadline = target_week["deadline"] if target_week else get_planning_deadline()
    week_label = target_week["week_label"] if target_week else f"Week {week_index}"
    started_at = get_planning_started_at()
    slots = get_availability_slots(started_at, week_index)
    players = _get_players(week_index)
    suggestions = _get_suggested_dates(slots, players)

    embed = discord.Embed(
        title=f"📊 Planning summary - {week_label.lower()}",
        description=_build_description(deadline, players, week_index),
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="✅ Sure dates",
        value=_format_sure_dates(suggestions),
        inline=False,
    )
    embed.add_field(
        name="🔵 Probable dates",
        value=_format_probable_dates(suggestions),
        inline=False,
    )

    if not players:
        embed.add_field(
            name="🧑‍🤝‍🧑 Players",
            value="No registered players found.",
            inline=False,
        )
        return embed

    for player in players.values():
        embed.add_field(
            name=player.nickname,
            value=_format_player(player, slots),
            inline=False,
        )

    return embed


def get_suggested_dates() -> list[SuggestedDate]:
    return get_week_suggested_dates(1)


def get_week_suggested_dates(week_index: int) -> list[SuggestedDate]:
    started_at = get_planning_started_at()
    slots = get_availability_slots(started_at, week_index)
    players = _get_players(week_index)

    if not players:
        return []

    return _get_suggested_dates(slots, players)


def _get_suggested_dates(
    slots: list[tuple[str, str]],
    players: dict[int, PlayerAvailability],
) -> list[SuggestedDate]:
    suggestions = []
    for slot_key, label in slots:
        statuses = [
            player.statuses.get(slot_key)
            for player in players.values()
        ]

        slot_datetime = _find_slot_datetime(slot_key)

        if all(status == "available" for status in statuses):
            suggestions.append(SuggestedDate(slot_key, label, slot_datetime, "sure"))
            continue

        if any(status not in ("available", "doubtful") for status in statuses):
            continue
        if "doubtful" not in statuses:
            continue

        doubtful_players = [
            player.nickname
            for player in players.values()
            if player.statuses.get(slot_key) == "doubtful"
        ]
        suggestions.append(
            SuggestedDate(slot_key, label, slot_datetime, "probable", doubtful_players)
        )

    return suggestions


def _find_slot_datetime(slot_key: str) -> datetime:
    started_at = get_planning_started_at()
    week_index = _slot_week_index(slot_key)
    for candidate_datetime, candidate_key, label in get_availability_slot_details(
        started_at,
        week_index,
    ):
        if candidate_key == slot_key:
            return candidate_datetime

    raise ValueError(f"Unknown availability slot: {slot_key}")


def _slot_week_index(slot_key: str) -> int:
    prefix = slot_key.split(":", maxsplit=1)[0]
    if not prefix.startswith("week_"):
        return 1

    return int(prefix.removeprefix("week_"))


def _get_players(week_index: int) -> dict[int, PlayerAvailability]:
    rows = get_planning_summary_rows(week_index)
    players: dict[int, PlayerAvailability] = {}

    for row in rows:
        user_id = row["user_id"]
        player = players.setdefault(
            user_id,
            PlayerAvailability(nickname=row["nickname"], note=row["note"]),
        )

        if row["slot_key"] and row["status"]:
            player.statuses[row["slot_key"]] = row["status"]

    return players


def _build_description(
    deadline: datetime | None,
    players: dict[int, PlayerAvailability],
    week_index: int,
) -> str:
    lines = [f"🧑‍🤝‍🧑 Registered players: **{len(players)}**"]
    if deadline is not None:
        lines.append(f"⏳ Deadline: **{deadline.strftime('%A %d/%m at %H:%M')}**")

    selected_slots = get_selected_planning_slots(week_index)
    if selected_slots:
        selected_labels = ", ".join(
            selected_slot["slot_label"]
            for selected_slot in selected_slots
        )
        lines.append(f"📅 Selected dates: **{selected_labels}**")
        recap_nickname = selected_slots[0].get("recap_nickname")
        if recap_nickname:
            lines.append(f"📜 Recap: **{recap_nickname}**")
    else:
        target_week = get_planning_week(week_index)
        if target_week and target_week["no_session_selected_at"] is not None:
            lines.append("🛌 Selected dates: **No session on this week**")

    return "\n".join(lines)


def _format_sure_dates(suggestions: list[SuggestedDate]) -> str:
    suggested_dates = [
        suggestion.label
        for suggestion in suggestions
        if suggestion.kind == "sure"
    ]

    return "\n".join(suggested_dates) if suggested_dates else "No sure date works for everyone."


def _format_probable_dates(suggestions: list[SuggestedDate]) -> str:
    probable_dates = [
        f"{suggestion.label} ({', '.join(f'{nickname} 🟦' for nickname in suggestion.doubtful_players)})"
        for suggestion in suggestions
        if suggestion.kind == "probable"
    ]

    return "\n".join(probable_dates) if probable_dates else "No probable date found."


def _format_player(
    player: PlayerAvailability,
    slots: list[tuple[str, str]],
) -> str:
    lines = []

    for status in ("available", "doubtful", "unavailable"):
        labels = [
            label
            for slot_key, label in slots
            if player.statuses.get(slot_key) == status
        ]
        lines.append(f"{STATUS_EMOJIS[status]} {', '.join(labels) if labels else '-'}")

    missing = [
        label
        for slot_key, label in slots
        if slot_key not in player.statuses
    ]
    lines.append(f"{STATUS_EMOJIS['missing']} {', '.join(missing) if missing else '-'}")

    if player.note:
        lines.append(f"📝 Note: {player.note}")

    return "\n".join(lines)
