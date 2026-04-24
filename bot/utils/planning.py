from datetime import datetime, time, timedelta


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


def get_availability_slots(started_at: datetime | None = None) -> list[tuple[str, str]]:
    """
    Returns availability slots with fixed dates for the active planning window.
    """
    started_at = started_at or datetime.now()
    start_date = started_at.date()

    slots = []
    for slot_key, weekday, hour in AVAILABILITY_SLOT_SPECS:
        days_until = (weekday - start_date.weekday()) % 7
        slot_date = start_date + timedelta(days=days_until)
        slot_datetime = datetime.combine(slot_date, time(hour=hour))

        if slot_datetime < started_at:
            slot_date += timedelta(days=7)
            slot_datetime = datetime.combine(slot_date, time(hour=hour))

        label = f"{slot_datetime.strftime('%A')} {slot_date.strftime('%d/%m')} {hour}h"
        slots.append((slot_datetime, slot_key, label))

    return [(slot_key, label) for slot_datetime, slot_key, label in sorted(slots)]


def get_upcoming_week_days() -> list[datetime]:
    """
    Returns the next 7 days starting from today.
    """
    today = datetime.now().date()
    return [
        datetime.combine(today + timedelta(days=i), datetime.min.time())
        for i in range(7)
    ]
