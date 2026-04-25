from psycopg.rows import dict_row

from bot.storage.db import get_connection


def get_profile(user_id: int) -> dict[str, str] | None:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                """
                SELECT nickname, race, player_class AS class
                FROM profiles
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()

    return dict(row) if row else None


def save_profile(user_id: int, nickname: str, race: str, player_class: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO profiles (user_id, nickname, race, player_class)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET nickname = EXCLUDED.nickname,
                race = EXCLUDED.race,
                player_class = EXCLUDED.player_class,
                updated_at = NOW()
            """,
            (user_id, nickname, race, player_class),
        )


def profile_exists(user_id: int) -> bool:
    return get_profile(user_id) is not None
