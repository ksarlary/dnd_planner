import logging
from datetime import timedelta

import discord

from bot.storage.planning import (
    get_registered_players,
    get_selected_planning_slots,
    set_selected_planning_slots,
)
from bot.ui.availability_view import build_sessions_planned_embed
from bot.utils.availability_summary import SuggestedDate
from bot.utils.event_covers import get_random_event_cover_paths, read_event_cover
from bot.utils.time import as_app_timezone

log = logging.getLogger("discord-bot")


class PlanningSelectionView(discord.ui.View):
    def __init__(self, suggestions: list[SuggestedDate]):
        super().__init__(timeout=300)
        self.suggestions_by_key = {
            suggestion.slot_key: suggestion
            for suggestion in suggestions
        }

        if suggestions:
            self.add_item(PlanningSelectionSelect(suggestions))


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

        await interaction.response.defer(ephemeral=True, thinking=True)

        suggestions = [
            view.suggestions_by_key[slot_key]
            for slot_key in self.values
        ]
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

        set_selected_planning_slots(selected_slots)
        selected_labels = "\n".join(
            f"- {suggestion.label}"
            for suggestion in suggestions
        )
        await _notify_registered_players(interaction.client, [s.label for s in suggestions])
        if interaction.channel is not None and created_events:
            await _post_event_links(interaction.channel, created_events)

        await interaction.followup.send(
            f"Session date{'s' if len(suggestions) > 1 else ''} saved:\n{selected_labels}",
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
) -> None:
    embed = build_sessions_planned_embed(session_labels)

    for player in get_registered_players():
        user_id = player["user_id"]
        try:
            user = client.get_user(user_id) or await client.fetch_user(user_id)
            await user.send(embed=embed)
        except Exception:
            log.exception("Failed to send session notification to user_id=%s", user_id)


async def _post_event_links(
    channel: discord.abc.Messageable,
    created_events: list[tuple[str, str]],
) -> None:
    lines = [
        f"- **{label}**: {event_url}"
        for label, event_url in created_events
    ]
    await channel.send("Scheduled sessions:\n" + "\n".join(lines))


def _slot_week_index(slot_key: str) -> int:
    prefix = slot_key.split(":", maxsplit=1)[0]
    if not prefix.startswith("week_"):
        return 1

    return int(prefix.removeprefix("week_"))
