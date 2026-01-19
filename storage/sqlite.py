import sqlite3
import os

from storage.models import (
    USER_TABLE,
    HISTORY_TABLE,
    DECISIONS_TABLE,
    PROFILE_TABLE,
)

# Папка и путь к БД
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cnc.db")

# Создаём папку если нет
os.makedirs(BASE_DIR, exist_ok=True)

# Подключение
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


def init_db():
    """Инициализация всех таблиц"""
    cur.execute(USER_TABLE)
    cur.execute(HISTORY_TABLE)
    cur.execute(DECISIONS_TABLE)
    cur.execute(PROFILE_TABLE)
    conn.commit()


def get_connection():
    """Возвращает активное соединение"""
    return conn


def get_cursor():
    return conn.cursor()


# Автоинициализация при импорте
init_db()

print(f"✅ SQLite инициализирован: {DB_PATH}")
