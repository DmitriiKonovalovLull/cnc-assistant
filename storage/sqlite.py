import sqlite3
import os

# Папка для хранения базы
os.makedirs("storage", exist_ok=True)
db_path = "storage/cnc.db"

# Подключение к базе
conn = sqlite3.connect(db_path, check_same_thread=False)
cur = conn.cursor()

def init_db():
    # === Таблица пользователей ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            experience REAL DEFAULT 0.0
        )
    """)

    # === Таблица сессий ===
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

    # === Таблица истории сообщений ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            raw_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

# Инициализация базы
init_db()
print(f"✅ База CNC и таблицы созданы или проверены в '{db_path}'")
