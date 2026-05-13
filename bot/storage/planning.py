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
        conn.execute("DELETE FROM planning_selected_slots")


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


def get_registered_players() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT
                    user_id,
                    nickname,
                    race,
                    player_class AS class
                FROM profiles
                ORDER BY LOWER(nickname)
                """
            ).fetchall()

    return [dict(row) for row in rows]


def get_all_availabilities() -> dict[int, dict[str, str]]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT user_id, slot_key, status
                FROM planning_availabilities
                """
            ).fetchall()

    availabilities: dict[int, dict[str, str]] = {}
    for row in rows:
        availabilities.setdefault(row["user_id"], {})[row["slot_key"]] = row["status"]

    return availabilities


def get_all_availability_notes() -> dict[int, str]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT user_id, note
                FROM planning_notes
                """
            ).fetchall()

    return {row["user_id"]: row["note"] for row in rows}


def set_selected_planning_slot(
    slot_key: str,
    slot_label: str,
    manual_override: bool = False,
) -> None:
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT recap_user_id, recap_nickname
            FROM planning_selected_slots
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()

        conn.execute("DELETE FROM planning_selected_slots")
        conn.execute(
            """
            INSERT INTO planning_selected_slots (
                slot_key,
                slot_label,
                manual_override,
                recap_user_id,
                recap_nickname
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                slot_key,
                slot_label,
                manual_override,
                existing[0] if existing else None,
                existing[1] if existing else None,
            ),
        )


def get_selected_planning_slot() -> dict | None:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                """
                SELECT
                    slot_key,
                    slot_label,
                    manual_override,
                    recap_user_id,
                    recap_nickname,
                    created_at
                FROM planning_selected_slots
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()

    return dict(row) if row else None


def set_planning_recap_player(user_id: int, nickname: str) -> bool:
    with get_connection() as conn:
        selected = conn.execute(
            """
            SELECT slot_key, slot_label
            FROM planning_selected_slots
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if selected is None:
            return False

        cursor = conn.execute(
            """
            UPDATE planning_selected_slots
            SET recap_user_id = %s,
                recap_nickname = %s
            """,
            (user_id, nickname),
        )
        updated = cursor.rowcount > 0

        if updated:
            conn.execute(
                """
                INSERT INTO planning_recap_history (
                    user_id,
                    nickname,
                    slot_key,
                    slot_label
                )
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, nickname, selected[0], selected[1]),
            )

    return updated


def get_last_recap_player(
    exclude_slot_label: str | None = None,
    exclude_user_id: int | None = None,
) -> dict | None:
    params = []
    filters = []

    if exclude_slot_label is not None:
        filters.append("(slot_label IS DISTINCT FROM %s)")
        params.append(exclude_slot_label)

    if exclude_user_id is not None:
        filters.append("(user_id IS DISTINCT FROM %s)")
        params.append(exclude_user_id)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                f"""
                SELECT user_id, nickname, slot_key, slot_label, created_at
                FROM planning_recap_history
                {where_clause}
                ORDER BY created_at DESC
                LIMIT 1
                """,
                params,
            ).fetchone()

    return dict(row) if row else None
