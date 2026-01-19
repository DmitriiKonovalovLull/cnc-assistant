import sqlite3
import os
from datetime import datetime

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/db.sqlite", check_same_thread=False)
cur = conn.cursor()

# Таблица истории
cur.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    material TEXT,
    operation TEXT,
    diameter REAL,
    machine_type TEXT,
    rpm_mode TEXT,
    recommended_params TEXT,
    user_choice TEXT,
    valid BOOLEAN DEFAULT 1,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()


def save_history(user_id: int, session: dict):
    """Сохраняет запись в историю, session — словарь с параметрами"""
    cur = conn.cursor()

    material = session.get("material")
    operation = session.get("operation")
    diameter = session.get("diameter")
    machine_type = session.get("machine_type")
    rpm_mode = session.get("rpm_mode")
    recommended_params = session.get("recommended_params")
    user_choice = session.get("user_choice")
    valid = session.get("valid", True)

    # Конвертируем dict в строку, если есть
    for key in ["material", "operation", "machine_type", "rpm_mode",
                "recommended_params", "user_choice"]:
        value = locals()[key]
        if isinstance(value, dict):
            locals()[key] = str(value)

    cur.execute("""
        INSERT INTO history (
            user_id, material, operation, diameter,
            machine_type, rpm_mode, recommended_params,
            user_choice, valid
        ) VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        user_id, material, operation, diameter,
        machine_type, rpm_mode, recommended_params,
        user_choice, int(valid)
    ))
    conn.commit()
