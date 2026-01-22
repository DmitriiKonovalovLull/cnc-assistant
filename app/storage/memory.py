"""
Интерфейс для сохранения данных.
Объединяет in-memory хранилище и базу данных.
"""
import json
from typing import Dict, Any
from datetime import datetime

from app.storage.db import init_database, save_interaction_to_db
from app.services.experience import generate_learning_features

# Инициализация базы при импорте
init_database()


def save_interaction(interaction_data: Dict[str, Any]):
    """
    Сохранить взаимодействие.
    Основная точка сохранения данных для обучения.
    """
    # Генерируем ML фичи
    features = generate_learning_features(interaction_data)
    interaction_data['features'] = features

    # Сохраняем в базу данных
    try:
        interaction_id = save_interaction_to_db(interaction_data)
        print(f"✓ Взаимодействие сохранено (ID: {interaction_id})")
    except Exception as e:
        print(f"✗ Ошибка сохранения в БД: {e}")

        # Fallback: сохраняем в файл
        save_to_fallback_file(interaction_data)


def save_to_fallback_file(interaction_data: Dict[str, Any]):
    """Сохранить в файл как fallback."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"storage/fallback_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(interaction_data, f, ensure_ascii=False, indent=2)

        print(f"✓ Данные сохранены в файл: {filename}")
    except Exception as e:
        print(f"✗ Ошибка сохранения в файл: {e}")


def get_interaction_stats() -> Dict[str, Any]:
    """Получить статистику по собранным данным."""
    import sqlite3

    try:
        conn = sqlite3.connect("storage/cnc.db")
        cursor = conn.cursor()

        # Общее количество
        cursor.execute("SELECT COUNT(*) FROM interactions")
        total = cursor.fetchone()[0]

        # Количество с действиями пользователя
        cursor.execute("SELECT COUNT(*) FROM interactions WHERE user_rpm IS NOT NULL")
        with_actions = cursor.fetchone()[0]

        # Уникальные пользователи
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM interactions")
        unique_users = cursor.fetchone()[0]

        # Распределение по материалам
        cursor.execute('''
        SELECT material, COUNT(*) as count 
        FROM interactions 
        WHERE material IS NOT NULL 
        GROUP BY material 
        ORDER BY count DESC
        ''')
        materials = cursor.fetchall()

        conn.close()

        return {
            "total_interactions": total,
            "interactions_with_actions": with_actions,
            "unique_users": unique_users,
            "material_distribution": dict(materials),
            "collection_rate": with_actions / total if total > 0 else 0
        }

    except Exception as e:
        return {"error": str(e)}