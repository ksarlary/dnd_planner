from datetime import date, datetime, time, timedelta


AVAILABILITY_SLOT_SPECS = [
    ("monday_20", 0, 20),
    ("tuesday_20", 1, 20),
    ("wednesday_20", 2, 20),
    ("thursday_20", 3, 20),
    ("friday_20", 4, 20),
    ("saturday_14", 5, 14),
    ("saturday_20", 5, 20),
    ("sunday_14", 6, 14),
    ("sunday_20", 6, 20),
]


def get_target_week_start(started_at: datetime | None = None, week_index: int = 1) -> date:
    started_at = started_at or datetime.now()
    start_date = started_at.date()
    next_monday = start_date + timedelta(days=7 - start_date.weekday())
    return next_monday + timedelta(days=7 * (week_index - 1))


def get_target_week_label(week_start: date, week_index: int) -> str:
    return f"Week of {_format_day_month(week_start)}"


def _format_day_month(day: date) -> str:
    return f"{day.day}{_ordinal_suffix(day.day)} {day.strftime('%B')}"


def _ordinal_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"

    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def get_availability_slot_details(
    started_at: datetime | None = None,
    week_index: int = 1,
) -> list[tuple[datetime, str, str]]:
    """
    Returns dated availability slots for a target week after planning starts.
    """
    week_start = get_target_week_start(started_at, week_index)

    slots = []
    for slot_key, weekday, hour in AVAILABILITY_SLOT_SPECS:
        scoped_slot_key = f"week_{week_index}:{slot_key}"
        slot_date = week_start + timedelta(days=weekday)
        slot_datetime = datetime.combine(slot_date, time(hour=hour))

        label = f"{slot_datetime.strftime('%A')} {slot_date.strftime('%d/%m')} {hour}h"
        slots.append((slot_datetime, scoped_slot_key, label))

    return sorted(slots)


def get_availability_slots(
    started_at: datetime | None = None,
    week_index: int = 1,
) -> list[tuple[str, str]]:
    """
    Returns availability slots for a target week after planning starts.
    """
    return [
        (slot_key, label)
        for slot_datetime, slot_key, label in get_availability_slot_details(
            started_at,
            week_index,
        )
    ]


def get_upcoming_week_days() -> list[datetime]:
    """
    Returns the next 7 days starting from today.
    """
    today = datetime.now().date()
    return [
        datetime.combine(today + timedelta(days=i), datetime.min.time())
        for i in range(7)
    ]


def get_deadline_days_before_target_week(week_index: int) -> list[datetime]:
    """
    Returns the Monday-Sunday deadline window before a target week starts.
    """
    target_week_start = get_target_week_start(week_index=week_index)
    deadline_week_start = target_week_start - timedelta(days=7)
    return [
        datetime.combine(deadline_week_start + timedelta(days=i), datetime.min.time())
        for i in range(7)
    ]
