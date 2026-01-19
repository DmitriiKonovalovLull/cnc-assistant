import sqlite3
import os

os.makedirs("data", exist_ok=True)

conn = sqlite3.connect("data/cnc.db", check_same_thread=False)

def init_db():
    cur = conn.cursor()
    # таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            experience REAL DEFAULT 0.0
        )
    """)
    # таблица истории
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            raw_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

init_db()
