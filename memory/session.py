import sqlite3
import os

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/cnc.db", check_same_thread=False)

# === Инициализация таблицы sessions ===
def init_sessions_table():
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            material TEXT,
            material_name TEXT,
            operation TEXT,
            diameter REAL,
            machine_type TEXT,
            rpm_mode TEXT,
            state TEXT DEFAULT 'IDLE',
            username TEXT,
            max_rpm_turning INTEGER DEFAULT 3000,
            max_rpm_milling INTEGER DEFAULT 12000
        )
    """)
    conn.commit()

init_sessions_table()


# === Функции работы с сессиями ===
def get_session(user_id: int) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row:
        columns = [col[1] for col in cur.execute("PRAGMA table_info(sessions)")]
        return dict(zip(columns, row))
    else:
        cur.execute("INSERT INTO sessions (user_id, state) VALUES (?, ?)", (user_id, "IDLE"))
        conn.commit()
        return get_session(user_id)


def update_session(user_id: int, clear=False, **kwargs):
    cur = conn.cursor()
    if clear:
        cur.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        conn.commit()
        return
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    cur.execute(f"UPDATE sessions SET {fields} WHERE user_id=?", values)
    conn.commit()
