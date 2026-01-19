import sqlite3
import os
import json
from datetime import datetime

os.makedirs("data", exist_ok=True)

conn = sqlite3.connect("data/db.sqlite", check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ==========================================================
# HISTORY = ДАТАСЕТ РЕШЕНИЙ (ДЕНЬ 3)
# ==========================================================
cur.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,

    -- Контекст
    material TEXT,
    operation TEXT,
    diameter REAL,
    machine_type TEXT,
    rpm_mode TEXT,

    -- Рекомендация бота
    recommended_params TEXT,   -- JSON

    -- Фактический выбор пользователя
    user_choice TEXT,          -- JSON

    -- Оценка применимости данных (НЕ человека)
    valid BOOLEAN DEFAULT 1,
    confidence REAL DEFAULT 1.0,

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# ==========================================================
# СОХРАНЕНИЕ ИСТОРИИ (КЛЮЧЕВАЯ ФУНКЦИЯ ДНЯ 3)
# ==========================================================
def save_history(
    user_id: int,
    context: dict,
    recommendation: dict,
    user_choice: dict,
    valid: bool = True,
    confidence: float = 1.0
):
    """
    Сохраняет ОДНО ИНЖЕНЕРНОЕ РЕШЕНИЕ пользователя.
    НЕ лог диалога, а обучающий пример.
    """

    cur.execute("""
        INSERT INTO history (
            user_id,
            material,
            operation,
            diameter,
            machine_type,
            rpm_mode,
            recommended_params,
            user_choice,
            valid,
            confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        context.get("material"),
        context.get("operation"),
        context.get("diameter"),
        context.get("machine_type"),
        context.get("rpm_mode"),
        json.dumps(recommendation, ensure_ascii=False),
        json.dumps(user_choice, ensure_ascii=False),
        int(valid),
        float(confidence)
    ))

    conn.commit()
