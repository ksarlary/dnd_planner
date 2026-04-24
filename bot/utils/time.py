import os
from datetime import datetime
from zoneinfo import ZoneInfo


def get_app_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Paris"))


def now() -> datetime:
    return datetime.now(get_app_timezone()).replace(tzinfo=None)


def as_app_timezone(value: datetime) -> datetime:
    return value.replace(tzinfo=get_app_timezone())
