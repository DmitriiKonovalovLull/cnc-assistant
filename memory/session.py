# ===============================
# session.py — с долгой памятью через SQLite
# ===============================
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any

DB_PATH = "storage/cnc.db"

DEFAULT_SESSION = {
    "state": "IDLE",

    # Слоты
    "material": None,
    "material_name": None,
    "operation": None,
    "cut_type": None,
    "diameter": None,
    "machine_type": None,
    "rpm_mode": None,
    "max_rpm_turning": None,
    "max_rpm_milling": None,

    # Метаданные
    "created_at": None,
    "updated_at": None,
}


def _ensure_table():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            data TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_session(user_id: int) -> Dict[str, Any]:
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT data FROM sessions WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])
    else:
        now = datetime.utcnow().isoformat()
        session = DEFAULT_SESSION.copy()
        session["created_at"] = now
        session["updated_at"] = now
        save_session(user_id, session)
        return session


def save_session(user_id: int, session: Dict[str, Any]):
    session["updated_at"] = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO sessions (user_id, data) VALUES (?, ?)",
        (user_id, json.dumps(session))
    )
    conn.commit()
    conn.close()


def update_session(user_id: int, **kwargs):
    session = get_session(user_id)
    clear = kwargs.pop("clear", False)
    if clear:
        session = DEFAULT_SESSION.copy()
        session["created_at"] = datetime.utcnow().isoformat()
    session.update(kwargs)
    save_session(user_id, session)


def clear_session(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def set_state(user_id: int, state: str):
    update_session(user_id, state=state)


def debug_dump() -> Dict[int, Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id, data FROM sessions")
    rows = cur.fetchall()
    conn.close()
    return {user_id: json.loads(data) for user_id, data in rows}
