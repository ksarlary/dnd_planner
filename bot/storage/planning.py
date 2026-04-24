from datetime import datetime

from psycopg.rows import dict_row

from bot.storage.db import get_connection


def set_planning_deadline(deadline: datetime) -> None:
    started_at = datetime.now()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO planning (id, deadline, started_at)
            VALUES (1, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET deadline = EXCLUDED.deadline,
                started_at = EXCLUDED.started_at
            """,
            (deadline, started_at),
        )
        conn.execute("DELETE FROM planning_availabilities")
        conn.execute("DELETE FROM planning_notes")


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


def is_planning_open(now: datetime | None = None) -> bool:
    deadline = get_planning_deadline()
    if deadline is None:
        return False

    now = now or datetime.now()
    return now <= deadline


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


def save_user_availability(user_id: int, slot_key: str, status: str | None) -> bool:
    if not is_planning_open():
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


def save_user_availability_note(user_id: int, note: str) -> bool:
    if not is_planning_open():
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
