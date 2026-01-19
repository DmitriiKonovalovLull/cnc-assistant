import sqlite3
from storage.sqlite import get_connection

conn = get_connection()


def update_profile(user_id: int, delta: float, physics_valid: bool):
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO profiles (user_id)
        VALUES (?)
    """, (user_id,))

    cur.execute("""
        UPDATE profiles
        SET
            samples = samples + 1,
            avg_delta = (avg_delta * samples + ?) / (samples + 1),
            physics_valid_ratio =
                (physics_valid_ratio * samples + ?) / (samples + 1),
            last_updated = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (delta, int(physics_valid), user_id))

    conn.commit()
