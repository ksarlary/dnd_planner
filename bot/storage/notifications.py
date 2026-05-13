from psycopg.rows import dict_row

from bot.storage.db import get_connection


DEFAULT_NOTIFICATION_SETTINGS = {
    "dms_enabled": True,
    "availability_reminders_enabled": True,
    "session_reminders_enabled": True,
    "planned_session_messages_enabled": True,
}


def get_notification_settings(user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                """
                SELECT
                    user_id,
                    dms_enabled,
                    availability_reminders_enabled,
                    session_reminders_enabled,
                    planned_session_messages_enabled
                FROM notification_settings
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()

    if row:
        return dict(row)

    settings = {"user_id": user_id, **DEFAULT_NOTIFICATION_SETTINGS}
    save_notification_settings(user_id, settings)
    return settings


def save_notification_settings(user_id: int, settings: dict) -> dict:
    normalized = _normalize_settings(settings)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                """
                INSERT INTO notification_settings (
                    user_id,
                    dms_enabled,
                    availability_reminders_enabled,
                    session_reminders_enabled,
                    planned_session_messages_enabled
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET dms_enabled = EXCLUDED.dms_enabled,
                    availability_reminders_enabled = EXCLUDED.availability_reminders_enabled,
                    session_reminders_enabled = EXCLUDED.session_reminders_enabled,
                    planned_session_messages_enabled = EXCLUDED.planned_session_messages_enabled,
                    updated_at = NOW()
                RETURNING
                    user_id,
                    dms_enabled,
                    availability_reminders_enabled,
                    session_reminders_enabled,
                    planned_session_messages_enabled
                """,
                (
                    user_id,
                    normalized["dms_enabled"],
                    normalized["availability_reminders_enabled"],
                    normalized["session_reminders_enabled"],
                    normalized["planned_session_messages_enabled"],
                ),
            ).fetchone()

    return dict(row)


def update_notification_setting(user_id: int, key: str, value: bool) -> dict:
    settings = get_notification_settings(user_id)
    settings[key] = value
    return save_notification_settings(user_id, settings)


def allows_availability_reminders(user_id: int) -> bool:
    settings = get_notification_settings(user_id)
    return (
        settings["dms_enabled"]
        and settings["availability_reminders_enabled"]
    )


def allows_session_reminders(user_id: int) -> bool:
    settings = get_notification_settings(user_id)
    return (
        settings["dms_enabled"]
        and settings["session_reminders_enabled"]
    )


def allows_planned_session_messages(user_id: int) -> bool:
    settings = get_notification_settings(user_id)
    return (
        settings["dms_enabled"]
        and settings["planned_session_messages_enabled"]
    )


def _normalize_settings(settings: dict) -> dict:
    normalized = {
        key: bool(settings.get(key, default))
        for key, default in DEFAULT_NOTIFICATION_SETTINGS.items()
    }

    if not normalized["dms_enabled"]:
        normalized["availability_reminders_enabled"] = False
        normalized["session_reminders_enabled"] = False
        normalized["planned_session_messages_enabled"] = False

    return normalized
