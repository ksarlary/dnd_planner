import logging
from datetime import timedelta

import discord

from bot.storage.planning import (
    get_last_recap_player,
    get_planning_week,
    get_registered_players,
    get_selected_planning_slots,
    record_recap_player,
    set_selected_planning_slots,
    set_no_session_for_week,
)
from bot.ui.availability_view import (
    build_no_session_planned_embed,
    build_sessions_planned_embed,
)
from bot.utils.availability_summary import SuggestedDate
from bot.utils.availability_taunts import build_low_availability_taunt
from bot.utils.event_covers import get_random_event_cover_paths, read_event_cover
from bot.utils.time import as_app_timezone

log = logging.getLogger("discord-bot")

RECAP_ROTATION = "Sonia -> Shin -> Atouf -> Balico"


class PlanningSelectionView(discord.ui.View):
    def __init__(self, suggestions: list[SuggestedDate], week_index: int):
        super().__init__(timeout=300)
        self.week_index = week_index
        self.suggestions_by_key = {
            suggestion.slot_key: suggestion
            for suggestion in suggestions
        }

        if suggestions:
            self.add_item(PlanningSelectionSelect(suggestions))
        self.add_item(NoSessionButton(week_index))


class PlanningSelectionSelect(discord.ui.Select):
    def __init__(self, suggestions: list[SuggestedDate]):
        options = [
            discord.SelectOption(
                label=suggestion.label,
                value=suggestion.slot_key,
                description=_build_description(suggestion),
                emoji="✅" if suggestion.kind == "sure" else "🔵",
            )
            for suggestion in suggestions[:25]
        ]

        super().__init__(
            placeholder="Pick up to 2 session dates",
            min_values=1,
            max_values=min(2, len(options)),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, PlanningSelectionView):
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "Session dates must be selected from the server so events can be created.",
                ephemeral=True,
            )
            return

        suggestions = [
            view.suggestions_by_key[slot_key]
            for slot_key in self.values
        ]
        players = get_registered_players()
        if not players:
            await interaction.response.send_message(
                "No registered players found for recap duty.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            embed=_build_recap_selection_embed(suggestions),
            view=RecapSelectionView(suggestions),
        )


class RecapSelectionView(discord.ui.View):
    def __init__(self, suggestions: list[SuggestedDate]):
        super().__init__(timeout=300)
        self.suggestions = suggestions
        self.add_item(RecapSelectionSelect())


class RecapSelectionSelect(discord.ui.Select):
    def __init__(self):
        players = get_registered_players()
        options = [
            discord.SelectOption(
                label=player["nickname"],
                value=str(player["user_id"]),
                description=_truncate_option_description(
                    f"{player['race']} {player['class']}"
                ),
                emoji="📜",
            )
            for player in players[:25]
        ]

        super().__init__(
            placeholder="Pick who does the previous session recap",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, RecapSelectionView):
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "Session dates must be selected from the server so events can be created.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        players = get_registered_players()
        recap_player = next(
            (
                player
                for player in players
                if str(player["user_id"]) == self.values[0]
            ),
            None,
        )
        if recap_player is None:
            await interaction.followup.send(
                "That recap player is no longer registered.",
                ephemeral=True,
            )
            return

        suggestions = view.suggestions
        week_index = _slot_week_index(suggestions[0].slot_key)
        await _delete_previous_events(interaction.guild, week_index)
        event_cover_paths = get_random_event_cover_paths(len(suggestions))

        selected_slots = []
        created_events = []
        for index, suggestion in enumerate(suggestions):
            event_cover = (
                read_event_cover(event_cover_paths[index])
                if event_cover_paths
                else None
            )
            event = await _create_scheduled_event(
                interaction.guild,
                suggestion,
                event_cover,
            )
            selected_slots.append(
                {
                    "slot_key": suggestion.slot_key,
                    "slot_label": suggestion.label,
                    "session_datetime": suggestion.session_datetime,
                    "guild_id": interaction.guild.id,
                    "event_id": event.id if event else None,
                }
            )
            if event:
                created_events.append(
                    (
                        suggestion.label,
                        f"https://discord.com/events/{interaction.guild.id}/{event.id}",
                    )
                )

        set_selected_planning_slots(selected_slots, recap_player)
        record_recap_player(recap_player)
        selected_labels = "\n".join(
            f"- {suggestion.label}"
            for suggestion in suggestions
        )
        taunt = (
            build_low_availability_taunt(week_index)
            if len(suggestions) == 1
            else None
        )
        await _notify_registered_players(
            interaction.client,
            [s.label for s in suggestions],
            taunt,
            recap_player["nickname"],
        )
        if interaction.channel is not None and created_events:
            await _post_event_links(
                interaction.channel,
                created_events,
                taunt,
                recap_player["nickname"],
            )

        await interaction.followup.send(
            f"✅ Session date{'s' if len(suggestions) > 1 else ''} saved:\n"
            f"{selected_labels}\n"
            f"📜 Recap: {recap_player['nickname']}",
            ephemeral=True,
        )


class NoSessionButton(discord.ui.Button):
    def __init__(self, week_index: int):
        self.week_index = week_index
        super().__init__(
            label="No session on chosen week",
            style=discord.ButtonStyle.danger,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "This must be selected from the server so previous events can be cleaned up.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        await _delete_previous_events(interaction.guild, self.week_index)
        set_no_session_for_week(self.week_index)

        target_week = get_planning_week(self.week_index)
        week_label = target_week["week_label"] if target_week else f"week {self.week_index}"
        taunt = build_low_availability_taunt(self.week_index)
        await _notify_registered_players_no_session(
            interaction.client,
            week_label,
            taunt,
        )
        if interaction.channel is not None:
            await _post_no_session_message(interaction.channel, week_label, taunt)

        await interaction.followup.send(
            f"🛌 No session saved for {week_label.lower()}. Players have been notified.",
            ephemeral=True,
        )


def _build_description(suggestion: SuggestedDate) -> str:
    if suggestion.kind == "sure":
        return "Sure date: everyone is available"

    doubtful = ", ".join(suggestion.doubtful_players)
    if len(doubtful) > 90:
        doubtful = doubtful[:87] + "..."

    return f"Probable date: doubtful - {doubtful}"


async def _create_scheduled_event(
    guild: discord.Guild,
    suggestion: SuggestedDate,
    event_cover: bytes | None,
) -> discord.ScheduledEvent | None:
    start_time = as_app_timezone(suggestion.session_datetime)
    end_time = start_time + timedelta(hours=4)

    try:
        event = await guild.create_scheduled_event(
            name=f"DnD session - {suggestion.label}",
            description="Planned by Goblin Scheduler.",
            start_time=start_time,
            end_time=end_time,
            entity_type=discord.EntityType.external,
            privacy_level=discord.PrivacyLevel.guild_only,
            location="Discord",
            image=event_cover,
        )
        return event
    except Exception:
        log.exception("Failed to create scheduled event for %s", suggestion.label)
        return None


async def _delete_previous_events(guild: discord.Guild, week_index: int) -> None:
    for selected_slot in get_selected_planning_slots(week_index):
        event_id = selected_slot.get("event_id")
        if not event_id:
            continue

        try:
            event = await guild.fetch_scheduled_event(event_id)
            await event.delete()
        except Exception:
            log.exception("Failed to delete previous scheduled event_id=%s", event_id)


async def _notify_registered_players(
    client: discord.Client,
    session_labels: list[str],
    taunt: str | None = None,
    recap_nickname: str | None = None,
) -> None:
    embed = build_sessions_planned_embed(session_labels, taunt, recap_nickname)

    for player in get_registered_players():
        user_id = player["user_id"]
        try:
            user = client.get_user(user_id) or await client.fetch_user(user_id)
            await user.send(embed=embed)
        except Exception:
            log.exception("Failed to send session notification to user_id=%s", user_id)


async def _notify_registered_players_no_session(
    client: discord.Client,
    week_label: str,
    taunt: str | None = None,
) -> None:
    embed = build_no_session_planned_embed(week_label, taunt)

    for player in get_registered_players():
        user_id = player["user_id"]
        try:
            user = client.get_user(user_id) or await client.fetch_user(user_id)
            await user.send(embed=embed)
        except Exception:
            log.exception("Failed to send no-session notification to user_id=%s", user_id)


async def _post_event_links(
    channel: discord.abc.Messageable,
    created_events: list[tuple[str, str]],
    taunt: str | None = None,
    recap_nickname: str | None = None,
) -> None:
    lines = [
        f"- **{label}**: {event_url}"
        for label, event_url in created_events
    ]
    if taunt:
        lines.append("")
        lines.append(f"🪶 Calendar blame: {taunt}")
    if recap_nickname:
        lines.append(f"📜 Recap: {recap_nickname}")
    await channel.send("🎲 Scheduled sessions:\n" + "\n".join(lines))


async def _post_no_session_message(
    channel: discord.abc.Messageable,
    week_label: str,
    taunt: str | None = None,
) -> None:
    lines = [f"🛌 No session planned for **{week_label.lower()}**."]
    if taunt:
        lines.append(f"🪶 Calendar blame: {taunt}")

    await channel.send("\n".join(lines))


def _slot_week_index(slot_key: str) -> int:
    prefix = slot_key.split(":", maxsplit=1)[0]
    if not prefix.startswith("week_"):
        return 1

    return int(prefix.removeprefix("week_"))


def _build_recap_selection_embed(suggestions: list[SuggestedDate]) -> discord.Embed:
    selected_dates = "\n".join(
        f"- {suggestion.label}"
        for suggestion in suggestions
    )
    last_recap_player = get_last_recap_player()
    last_recap_text = (
        last_recap_player["nickname"]
        if last_recap_player
        else "Nobody yet"
    )

    embed = discord.Embed(
        title="📜 Choose recap duty",
        description=(
            "Pick who will recap the previous session before these dates are announced."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(name="📅 Selected sessions", value=selected_dates, inline=False)
    embed.add_field(name="🔁 Recap order", value=RECAP_ROTATION, inline=False)
    embed.add_field(name="🕯️ Last recap", value=last_recap_text, inline=False)
    return embed


def _truncate_option_description(description: str) -> str:
    if len(description) <= 100:
        return description

    return description[:97] + "..."
