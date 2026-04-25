import random

from bot.storage.planning import (
    get_planning_started_at,
    get_registered_players,
    get_user_availabilities,
)
from bot.utils.planning import get_availability_slots


TAUNT_TEMPLATES = [
    "Put the blame on the {label}. The calendar insists.",
    "Somewhere, a {label} has made scheduling everyone else's problem.",
    "The {label} has selected the ancient technique: be unavailable.",
    "If the party needs a culprit, the {label} is looking suspiciously calendar-shaped.",
    "The council gently side-eyes the {label}.",
    "A {label} looked at the schedule and chose chaos.",
    "The {label} has clearly multiclassed into Scheduling Obstacle.",
    "History will remember the {label}. Probably not kindly.",
    "The {label} has cast *Greater Inconvenience*. It's super effective.",
    "Bards will sing of the {label}... mostly complaints.",
    "The {label} rolled a natural 1 on availability.",
    "Legends say the {label} almost showed up once.",
    "The {label} is currently tanking the schedule. Not their best role.",
    "A wild {label} appeared… and immediately fled the calendar.",
    "The {label} has entered stealth mode (permanently).",
    "The {label} is fighting the final boss: basic planning.",
    "The {label} has been banned from the timeline for crimes against scheduling.",
    "Scholars are still debating the {label}'s commitment to showing up.",
    "The {label} critically failed their appointment saving throw.",
    "Rumor has it the {label} schedules things in a parallel universe.",
    "The {label} has unlocked the achievement: 'Nowhere, Ever'.",
    "The {label} has gone AFK in real life.",
    "The {label} heard 'session time' and chose violence.",
    "Even the dice refuse to roll for the {label}'s availability.",
    "The {label} is roleplaying as 'unreachable NPC'.",
    "The {label} has successfully avoided all forms of responsibility.",
    "The {label} took 'free time' very personally.",
    "The {label} is on a side quest: not attending.",
    "The {label} has mastered the art of not being there.",
]


def build_low_availability_taunt(week_index: int) -> str | None:
    candidates = []
    started_at = get_planning_started_at()
    required_slot_keys = {
        slot_key
        for slot_key, label in get_availability_slots(started_at, week_index)
    }

    for player in get_registered_players():
        statuses = {
            slot_key: status
            for slot_key, status in get_user_availabilities(player["user_id"]).items()
            if slot_key in required_slot_keys
        }
        available_count = sum(
            1
            for status in statuses.values()
            if status == "available"
        )

        if not statuses or available_count <= 1:
            candidates.append(player)

    if not candidates:
        return None

    player = random.choice(candidates)
    label_key = random.choice(("race", "class"))
    label = player.get(label_key) or "adventurer"
    template = random.choice(TAUNT_TEMPLATES)
    return template.format(label=label.lower())
