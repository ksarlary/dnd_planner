from datetime import date, datetime, timedelta

from psycopg.rows import dict_row

from bot.storage.db import get_connection
from bot.utils.time import now as app_now
from bot.utils.planning import get_target_week_label, get_target_week_start


def set_planning_deadline(
    deadline: datetime,
    week_count: int = 1,
    week_deadlines: dict[int, datetime] | None = None,
) -> None:
    started_at = app_now()
    week_count = max(1, min(2, week_count))
    week_deadlines = week_deadlines or {
        week_index: deadline for week_index in range(1, week_count + 1)
    }
    final_deadline = max(week_deadlines.values())

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO planning (
                id,
                deadline,
                started_at,
                notification_sent_at,
                selected_slot_key,
                selected_slot_label
            )
            VALUES (1, %s, %s, NULL, NULL, NULL)
            ON CONFLICT (id) DO UPDATE
            SET deadline = EXCLUDED.deadline,
                started_at = EXCLUDED.started_at,
                notification_sent_at = NULL,
                selected_slot_key = NULL,
                selected_slot_label = NULL
            """,
            (final_deadline, started_at),
        )
        conn.execute("DELETE FROM planning_availabilities")
        conn.execute("DELETE FROM planning_notes")
        conn.execute("DELETE FROM planning_reminders")
        conn.execute("DELETE FROM planning_selected_slots")
        conn.execute("DELETE FROM planning_target_weeks")
        for week_index in range(1, week_count + 1):
            week_start = get_target_week_start(started_at, week_index)
            week_deadline = week_deadlines.get(week_index, deadline)
            conn.execute(
                """
                INSERT INTO planning_target_weeks (
                    week_index,
                    week_start,
                    week_label,
                    deadline,
                    notification_sent_at
                )
                VALUES (%s, %s, %s, %s, NULL)
                """,
                (
                    week_index,
                    week_start,
                    get_target_week_label(week_start, week_index),
                    week_deadline,
                ),
            )


def get_planning_deadline() -> datetime | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT deadline
            FROM planning
            WHERE id = 1
            """
        ).fetchone()

    return row[0] if row else None


def get_planning_started_at() -> datetime | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT started_at
            FROM planning
            WHERE id = 1
            """
        ).fetchone()

    return row[0] if row else None


def get_planning_target_weeks() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT week_index, week_start, week_label, deadline, notification_sent_at
                FROM planning_target_weeks
                ORDER BY week_index
                """
            ).fetchall()

    return [dict(row) for row in rows]


def get_planning_week(week_index: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                """
                SELECT week_index, week_start, week_label, deadline, notification_sent_at
                FROM planning_target_weeks
                WHERE week_index = %s
                """,
                (week_index,),
            ).fetchone()

    return dict(row) if row else None


def get_planning_week_notification_states() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT week_index, week_label, deadline, notification_sent_at
                FROM planning_target_weeks
                ORDER BY week_index
                """
            ).fetchall()

    return [dict(row) for row in rows]


def mark_planning_week_notification_sent(week_index: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE planning_target_weeks
            SET notification_sent_at = NOW()
            WHERE week_index = %s
            """,
            (week_index,),
        )


def set_selected_planning_slots(slots: list[dict]) -> None:
    limited_slots = slots[:2]
    week_prefix = None
    if limited_slots:
        week_prefix = limited_slots[0]["slot_key"].split(":", maxsplit=1)[0]

    with get_connection() as conn:
        if week_prefix:
            conn.execute(
                """
                DELETE FROM planning_selected_slots
                WHERE slot_key LIKE %s
                """,
                (f"{week_prefix}:%",),
            )
        else:
            conn.execute("DELETE FROM planning_selected_slots")

        for position, slot in enumerate(limited_slots, start=1):
            conn.execute(
                """
                INSERT INTO planning_selected_slots (
                    slot_key,
                    slot_label,
                    position,
                    session_datetime,
                    guild_id,
                    event_id,
                    notification_sent_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    slot["slot_key"],
                    slot["slot_label"],
                    position,
                    slot["session_datetime"],
                    slot["guild_id"],
                    slot.get("event_id"),
                ),
            )

        if limited_slots:
            first_slot = limited_slots[0]
            conn.execute(
                """
                UPDATE planning
                SET selected_slot_key = %s,
                    selected_slot_label = %s
                WHERE id = 1
                """,
                (first_slot["slot_key"], first_slot["slot_label"]),
            )
        else:
            conn.execute(
                """
                UPDATE planning
                SET selected_slot_key = NULL,
                    selected_slot_label = NULL
                WHERE id = 1
                """
            )


def get_selected_planning_slots(week_index: int | None = None) -> list[dict]:
    params = ()
    where_clause = ""
    if week_index is not None:
        where_clause = "WHERE slot_key LIKE %s"
        params = (f"week_{week_index}:%",)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                f"""
                SELECT
                    slot_key,
                    slot_label,
                    position,
                    session_datetime,
                    guild_id,
                    event_id,
                    notification_sent_at,
                    reminder_sent_at
                FROM planning_selected_slots
                {where_clause}
                ORDER BY position
                """,
                params,
            ).fetchall()

    return [dict(row) for row in rows]


def get_sessions_needing_day_before_reminder(current_time: datetime) -> list[dict]:
    tomorrow = current_time.date() + timedelta(days=1)

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT slot_key, slot_label, position, session_datetime, guild_id, event_id
                FROM planning_selected_slots
                WHERE session_datetime::date = %s
                    AND reminder_sent_at IS NULL
                ORDER BY position
                """,
                (tomorrow,),
            ).fetchall()

    return [dict(row) for row in rows]


def mark_session_day_before_reminder_sent(slot_key: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE planning_selected_slots
            SET reminder_sent_at = NOW()
            WHERE slot_key = %s
            """,
            (slot_key,),
        )


def is_planning_open(
    now: datetime | None = None,
    week_index: int | None = None,
    slot_key: str | None = None,
) -> bool:
    current_time = now or app_now()

    if slot_key is not None:
        week_index = _slot_week_index(slot_key)

    if week_index is not None:
        target_week = get_planning_week(week_index)
        if not target_week or target_week["deadline"] is None:
            return False

        return current_time <= target_week["deadline"]

    target_weeks = get_planning_target_weeks()
    if target_weeks:
        return any(
            target_week["deadline"] is not None
            and current_time <= target_week["deadline"]
            for target_week in target_weeks
        )

    deadline = get_planning_deadline()
    return deadline is not None and current_time <= deadline


def get_user_availabilities(user_id: int) -> dict[str, str]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT slot_key, status
                FROM planning_availabilities
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchall()

    return {row["slot_key"]: row["status"] for row in rows}


def get_planning_summary_rows() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT
                    p.user_id,
                    p.nickname,
                    pn.note,
                    pa.slot_key,
                    pa.status
                FROM profiles p
                LEFT JOIN planning_notes pn ON pn.user_id = p.user_id
                LEFT JOIN planning_availabilities pa ON pa.user_id = p.user_id
                ORDER BY LOWER(p.nickname), p.user_id, pa.slot_key
                """
            ).fetchall()

    return [dict(row) for row in rows]


def get_registered_players() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT user_id, nickname
                FROM profiles
                ORDER BY LOWER(nickname), user_id
                """
            ).fetchall()

    return [dict(row) for row in rows]


def get_players_with_missing_availabilities(required_slot_keys: list[str]) -> list[dict]:
    players = get_registered_players()
    if not players:
        return []

    missing_players = []
    for player in players:
        statuses = get_user_availabilities(player["user_id"])
        missing_slots = [
            slot_key
            for slot_key in required_slot_keys
            if slot_key not in statuses
        ]
        if missing_slots:
            player["missing_slot_keys"] = missing_slots
            missing_players.append(player)

    return missing_players


def was_planning_reminder_sent(user_id: int, reminder_date: date) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM planning_reminders
            WHERE user_id = %s AND reminder_date = %s
            """,
            (user_id, reminder_date),
        ).fetchone()

    return row is not None


def mark_planning_reminder_sent(user_id: int, reminder_date: date) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO planning_reminders (user_id, reminder_date)
            VALUES (%s, %s)
            ON CONFLICT (user_id, reminder_date) DO NOTHING
            """,
            (user_id, reminder_date),
        )


def save_user_availability(user_id: int, slot_key: str, status: str | None) -> bool:
    if not is_planning_open(slot_key=slot_key):
        return False

    with get_connection() as conn:
        if status is None:
            conn.execute(
                """
                DELETE FROM planning_availabilities
                WHERE user_id = %s AND slot_key = %s
                """,
                (user_id, slot_key),
            )
            return True

        conn.execute(
            """
            INSERT INTO planning_availabilities (user_id, slot_key, status)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, slot_key) DO UPDATE
            SET status = EXCLUDED.status,
                updated_at = NOW()
            """,
            (user_id, slot_key, status),
        )
        return True


def get_user_availability_note(user_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT note
            FROM planning_notes
            WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()

    return row[0] if row else None


def save_user_availability_note(
    user_id: int,
    note: str,
    week_index: int | None = None,
) -> bool:
    if not is_planning_open(week_index=week_index):
        return False

    note = note.strip()

    with get_connection() as conn:
        if not note:
            conn.execute(
                """
                DELETE FROM planning_notes
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return True

        conn.execute(
            """
            INSERT INTO planning_notes (user_id, note)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET note = EXCLUDED.note,
                updated_at = NOW()
            """,
            (user_id, note),
        )
        return True


def _slot_week_index(slot_key: str) -> int:
    prefix = slot_key.split(":", maxsplit=1)[0]
    if not prefix.startswith("week_"):
        return 1

    return int(prefix.removeprefix("week_"))
