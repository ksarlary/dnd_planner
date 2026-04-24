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
                started_at TIMESTAMP NOT NULL DEFAULT NOW()
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
                user_id BIGINT PRIMARY KEY,
                note TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
