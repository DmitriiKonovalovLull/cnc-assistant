"""
Инициализация базы данных.
"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def init_database(db_path: str = "storage/cnc.db"):
    """Инициализация базы данных."""
    # Создаем директорию если её нет
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Создаем таблицу для взаимодействий
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

        -- Контекст
        material TEXT NOT NULL,
        operation TEXT NOT NULL,
        mode TEXT NOT NULL,
        diameter REAL NOT NULL,

        -- Рекомендации
        recommended_vc REAL,
        recommended_rpm REAL,
        recommended_feed REAL,

        -- Действие пользователя
        user_rpm REAL,
        user_feed REAL,

        -- Результаты
        deviation_score REAL,
        decision_quality INTEGER, -- будет заполняться позже

        -- Контекст в JSON
        context_json TEXT,

        -- ML фичи
        features_json TEXT,

        -- Метаданные
        source TEXT DEFAULT 'telegram',
        session_id TEXT
    )
    ''')

    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON interactions (user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_material ON interactions (material)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON interactions (timestamp)')

    # Таблица для пользовательских метаданных
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_metadata (
        user_id TEXT PRIMARY KEY,
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        total_interactions INTEGER DEFAULT 0,
        inferred_machine_type TEXT,
        preferences_json TEXT,
        consistency_score REAL
    )
    ''')

    # Таблица для обратной связи (будет заполняться позже)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interaction_id INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

        -- Обратная связь от пользователя
        vibration_level INTEGER, -- 1-5
        surface_quality INTEGER, -- 1-5
        tool_wear_observed INTEGER, -- 1-5

        -- Системная оценка
        success_metric REAL,

        FOREIGN KEY (interaction_id) REFERENCES interactions (id)
    )
    ''')

    conn.commit()
    conn.close()

    print(f"База данных инициализирована: {db_path}")


def save_interaction_to_db(interaction_data: Dict[str, Any], db_path: str = "storage/cnc.db"):
    """Сохранить взаимодействие в базу данных."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Подготавливаем данные
    context = interaction_data.get("context", {})
    features = interaction_data.get("features", {})

    # Вставляем запись
    cursor.execute('''
    INSERT INTO interactions (
        user_id, material, operation, mode, diameter,
        recommended_vc, recommended_rpm, recommended_feed,
        user_rpm, user_feed, deviation_score,
        context_json, features_json, source
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        str(interaction_data.get("user_id", "unknown")),
        interaction_data.get("material", ""),
        interaction_data.get("operation", ""),
        interaction_data.get("mode", ""),
        interaction_data.get("diameter", 0),
        interaction_data.get("recommended_vc"),
        interaction_data.get("recommended_rpm"),
        interaction_data.get("recommended_feed"),
        interaction_data.get("user_rpm"),
        interaction_data.get("user_feed"),
        interaction_data.get("deviation_score"),
        json.dumps(context, ensure_ascii=False),
        json.dumps(features, ensure_ascii=False),
        interaction_data.get("source", "telegram")
    ))

    # Обновляем метаданные пользователя
    user_id = str(interaction_data.get("user_id", "unknown"))

    cursor.execute('''
    INSERT OR IGNORE INTO user_metadata (user_id) VALUES (?)
    ''', (user_id,))

    cursor.execute('''
    UPDATE user_metadata 
    SET last_seen = CURRENT_TIMESTAMP,
        total_interactions = total_interactions + 1
    WHERE user_id = ?
    ''', (user_id,))

    conn.commit()
    conn.close()

    return cursor.lastrowid


def get_user_interactions(
        user_id: str,
        limit: int = 100,
        db_path: str = "storage/cnc.db"
) -> List[Dict[str, Any]]:
    """Получить историю взаимодействий пользователя."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
    SELECT * FROM interactions 
    WHERE user_id = ? 
    ORDER BY timestamp DESC 
    LIMIT ?
    ''', (user_id, limit))

    rows = cursor.fetchall()
    conn.close()

    # Преобразуем в словари
    result = []
    for row in rows:
        item = dict(row)

        # Парсим JSON поля
        if item.get("context_json"):
            item["context"] = json.loads(item["context_json"])
            del item["context_json"]

        if item.get("features_json"):
            item["features"] = json.loads(item["features_json"])
            del item["features_json"]

        result.append(item)

    return result


def get_dataset_for_ml(
        limit: int = 1000,
        db_path: str = "storage/cnc.db"
) -> List[Dict[str, Any]]:
    """Получить датасет для обучения ML."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
    SELECT 
        material, operation, mode, diameter,
        recommended_rpm, user_rpm, deviation_score,
        features_json
    FROM interactions 
    WHERE user_rpm IS NOT NULL 
    AND recommended_rpm IS NOT NULL
    ORDER BY timestamp DESC 
    LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    # Формируем датасет
    dataset = []
    for row in rows:
        item = dict(row)

        if item.get("features_json"):
            features = json.loads(item["features_json"])
            item.update(features)
            del item["features_json"]

        dataset.append(item)

    return dataset


def export_to_csv(
        output_path: str = "data/dataset.csv",
        db_path: str = "storage/cnc.db"
):
    """Экспорт данных в CSV для анализа."""
    import pandas as pd

    conn = sqlite3.connect(db_path)

    # Читаем все взаимодействия
    query = '''
    SELECT 
        timestamp, user_id, material, operation, mode, diameter,
        recommended_vc, recommended_rpm, recommended_feed,
        user_rpm, user_feed, deviation_score, source
    FROM interactions
    WHERE user_rpm IS NOT NULL
    '''

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Сохраняем
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8')

    print(f"Данные экспортированы в {output_path}")
    print(f"Записей: {len(df)}")

    return df