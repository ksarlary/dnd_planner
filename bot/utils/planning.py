from datetime import datetime, timedelta


def get_upcoming_week_days() -> list[datetime]:
    """
    Returns the next 7 days starting from today.
    """
    today = datetime.now().date()
    return [
        datetime.combine(today + timedelta(days=i), datetime.min.time())
        for i in range(7)
    ]