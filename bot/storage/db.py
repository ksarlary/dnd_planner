import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import Connection


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set in environment.")

    return database_url


@contextmanager
def get_connection() -> Iterator[Connection]:
    with psycopg.connect(get_database_url()) as conn:
        yield conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id BIGINT PRIMARY KEY,
                nickname TEXT NOT NULL,
                race TEXT NOT NULL,
                player_class TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                deadline TIMESTAMP NOT NULL,
                started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                notification_sent_at TIMESTAMP,
                selected_slot_key TEXT,
                selected_slot_label TEXT
            )
            """
        )
        conn.execute(
            """
            ALTER TABLE planning
            ADD COLUMN IF NOT EXISTS started_at TIMESTAMP NOT NULL DEFAULT NOW()
            """
        )
        conn.execute(
            """
            ALTER TABLE planning
            ADD COLUMN IF NOT EXISTS notification_sent_at TIMESTAMP
            """
        )
        conn.execute(
            """
            ALTER TABLE planning
            ADD COLUMN IF NOT EXISTS selected_slot_key TEXT
            """
        )
        conn.execute(
            """
            ALTER TABLE planning
            ADD COLUMN IF NOT EXISTS selected_slot_label TEXT
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning_availabilities (
                user_id BIGINT NOT NULL,
                slot_key TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('available', 'doubtful', 'unavailable')
                ),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, slot_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning_notes (
                user_id BIGINT NOT NULL,
                week_index INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, week_index)
            )
            """
        )
        conn.execute(
            """
            ALTER TABLE planning_notes
            ADD COLUMN IF NOT EXISTS week_index INTEGER NOT NULL DEFAULT 1
            """
        )
        conn.execute("ALTER TABLE planning_notes DROP CONSTRAINT IF EXISTS planning_notes_pkey")
        conn.execute(
            """
            ALTER TABLE planning_notes
            ADD CONSTRAINT planning_notes_pkey PRIMARY KEY (user_id, week_index)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning_reminders (
                user_id BIGINT NOT NULL,
                reminder_date DATE NOT NULL,
                sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, reminder_date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_settings (
                user_id BIGINT PRIMARY KEY,
                dms_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                availability_reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                session_reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                planned_session_messages_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning_selected_slots (
                slot_key TEXT PRIMARY KEY,
                slot_label TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 1,
                session_datetime TIMESTAMP,
                guild_id BIGINT,
                event_id BIGINT,
                manual_override BOOLEAN NOT NULL DEFAULT FALSE,
                recap_user_id BIGINT,
                recap_nickname TEXT,
                notification_sent_at TIMESTAMPTZ,
                reminder_sent_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        for column_sql in (
            "ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 1",
            "ADD COLUMN IF NOT EXISTS session_datetime TIMESTAMP",
            "ADD COLUMN IF NOT EXISTS guild_id BIGINT",
            "ADD COLUMN IF NOT EXISTS event_id BIGINT",
            "ADD COLUMN IF NOT EXISTS manual_override BOOLEAN NOT NULL DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS recap_user_id BIGINT",
            "ADD COLUMN IF NOT EXISTS recap_nickname TEXT",
            "ADD COLUMN IF NOT EXISTS notification_sent_at TIMESTAMPTZ",
            "ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMPTZ",
        ):
            conn.execute(f"ALTER TABLE planning_selected_slots {column_sql}")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning_recap_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                nickname TEXT NOT NULL,
                slot_key TEXT,
                slot_label TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            ALTER TABLE planning_recap_history
            ADD COLUMN IF NOT EXISTS slot_key TEXT
            """
        )
        conn.execute(
            """
            ALTER TABLE planning_recap_history
            ADD COLUMN IF NOT EXISTS slot_label TEXT
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planning_target_weeks (
                week_index INTEGER PRIMARY KEY,
                week_start DATE NOT NULL,
                week_label TEXT NOT NULL,
                deadline TIMESTAMP,
                notification_sent_at TIMESTAMP,
                no_session_selected_at TIMESTAMPTZ
            )
            """
        )
        conn.execute(
            """
            ALTER TABLE planning_target_weeks
            ADD COLUMN IF NOT EXISTS deadline TIMESTAMP
            """
        )
        conn.execute(
            """
            ALTER TABLE planning_target_weeks
            ADD COLUMN IF NOT EXISTS notification_sent_at TIMESTAMP
            """
        )
        conn.execute(
            """
            ALTER TABLE planning_target_weeks
            ADD COLUMN IF NOT EXISTS no_session_selected_at TIMESTAMPTZ
            """
        )
