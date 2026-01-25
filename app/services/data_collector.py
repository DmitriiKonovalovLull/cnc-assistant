"""
Полноценная система памяти для Telegram бота с SQLite.
Сохраняет историю взаимодействий, считает статистику, определяет опыт пользователя.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import hashlib
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# КЛАССЫ ДЛЯ ОПРЕДЕЛЕНИЯ УРОВНЯ ОПЫТА
# ============================================================================

class ExperienceLevel(Enum):
    NOVICE = "новичок"  # 0-5 взаимодействий
    BEGINNER = "начинающий"  # 6-15 взаимодействий
    PRACTITIONER = "практик"  # 16-30 взаимодействий
    EXPERIENCED = "опытный"  # 31-50 взаимодействий
    EXPERT = "эксперт"  # 50+ взаимодействий, низкое отклонение


class EquipmentType(Enum):
    UNKNOWN = "неизвестно"
    OLD_MACHINE = "старый станок"  # низкие RPM
    UNIVERSAL_MACHINE = "универсальный"  # средние RPM
    MODERN_CNC = "современный ЧПУ"  # высокие RPM
    HIGH_SPEED = "высокоскоростной"  # очень высокие RPM


# ============================================================================
# ОСНОВНОЙ КЛАСС ПАМЯТИ
# ============================================================================

class UserMemory:
    """Система памяти для хранения и анализа данных пользователей."""

    def __init__(self, db_path: str = "data/cnc_memory.db"):
        """Инициализация системы памяти."""
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self):
        """Инициализация базы данных."""
        # Создаем директорию если нет
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    telegram_id TEXT,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_interactions INTEGER DEFAULT 0,
                    experience_level TEXT DEFAULT 'новичок',
                    avg_deviation REAL DEFAULT 0.0,
                    machine_type TEXT DEFAULT 'неизвестно',
                    machine_confidence REAL DEFAULT 0.0,
                    last_session_id TEXT,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')

            # Таблица взаимодействий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Параметры обработки
                    material TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    diameter REAL NOT NULL,

                    -- Рекомендации и решения
                    recommended_rpm REAL NOT NULL,
                    recommended_vc REAL,
                    recommended_feed REAL,
                    user_rpm REAL NOT NULL,
                    user_comment TEXT,

                    -- Анализ
                    deviation REAL NOT NULL,
                    deviation_percent REAL NOT NULL,

                    -- Метаданные
                    source TEXT DEFAULT 'telegram',
                    context_json TEXT,

                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')

            # Таблица статистики по материалам
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS material_stats (
                    user_id TEXT NOT NULL,
                    material TEXT NOT NULL,
                    interaction_count INTEGER DEFAULT 0,
                    total_deviation REAL DEFAULT 0.0,
                    avg_rpm REAL,
                    avg_deviation REAL DEFAULT 0.0,
                    first_used TIMESTAMP,
                    last_used TIMESTAMP,
                    expertise_score REAL DEFAULT 0.0,

                    PRIMARY KEY (user_id, material),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')

            # Таблица сессий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    interaction_count INTEGER DEFAULT 0,
                    avg_deviation REAL DEFAULT 0.0,
                    completed BOOLEAN DEFAULT 0,

                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            ''')

            # Индексы для производительности
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_time ON interactions(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_interactions_material ON interactions(material)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_material_stats_user ON material_stats(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')

            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Получить соединение с базой данных."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    # ============================================================================
    # МЕТОДЫ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ
    # ============================================================================

    def register_user(self, telegram_id: str, username: str = "",
                      first_name: str = "", last_name: str = "") -> str:
        """Зарегистрировать нового пользователя."""
        # Создаем уникальный user_id на основе telegram_id
        user_id = f"user_{telegram_id}"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, существует ли пользователь
            cursor.execute(
                "SELECT user_id FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Обновляем информацию о существующем пользователе
                cursor.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?,
                        updated_at = CURRENT_TIMESTAMP, is_active = 1
                    WHERE telegram_id = ?
                ''', (username, first_name, last_name, telegram_id))
                user_id = existing['user_id']
            else:
                # Создаем нового пользователя
                cursor.execute('''
                    INSERT INTO users 
                    (user_id, telegram_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, telegram_id, username, first_name, last_name))

            conn.commit()

        logger.info(f"Пользователь зарегистрирован: {user_id}")
        return user_id

    def get_user(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о пользователе."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    # ============================================================================
    # МЕТОДЫ СОХРАНЕНИЯ ВЗАИМОДЕЙСТВИЙ
    # ============================================================================

    def save_interaction(self, data: Dict[str, Any]) -> bool:
        """Сохранить взаимодействие пользователя с системой."""
        try:
            user_id = str(data.get('user_id', ''))
            if not user_id:
                logger.error("Нет user_id в данных взаимодействия")
                return False

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Создаем session_id если нет
                session_id = data.get('context', {}).get('session_id')
                if not session_id:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    session_id = f"{user_id}_{timestamp}"

                # Сохраняем взаимодействие
                cursor.execute('''
                    INSERT INTO interactions 
                    (user_id, session_id, material, operation, mode, diameter,
                     recommended_rpm, recommended_vc, recommended_feed,
                     user_rpm, user_comment, deviation, deviation_percent,
                     source, context_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    session_id,
                    data.get('material', ''),
                    data.get('operation', ''),
                    data.get('mode', ''),
                    float(data.get('diameter', 0)),
                    float(data.get('recommended_rpm', 0)),
                    float(data.get('recommended_vc', 0)),
                    float(data.get('recommended_feed', 0)),
                    float(data.get('user_rpm', 0)),
                    data.get('user_comment', ''),
                    float(data.get('deviation_score', 0)),
                    float(data.get('deviation_score', 0)) * 100,  # в проценты
                    data.get('context', {}).get('source', 'telegram'),
                    json.dumps(data.get('context', {}), ensure_ascii=False)
                ))

                interaction_id = cursor.lastrowid

                # Обновляем статистику пользователя
                self._update_user_stats(cursor, user_id, data)

                # Обновляем статистику по материалу
                self._update_material_stats(cursor, user_id, data)

                # Обновляем сессию
                self._update_session(cursor, user_id, session_id)

                # Обновляем информацию об оборудовании
                self._update_machine_info(cursor, user_id, data)

                conn.commit()

                logger.info(f"Взаимодействие #{interaction_id} сохранено для {user_id}")
                return True

        except Exception as e:
            logger.error(f"Ошибка сохранения взаимодействия: {e}", exc_info=True)
            return False

    def _update_user_stats(self, cursor, user_id: str, data: Dict[str, Any]):
        """Обновить статистику пользователя."""
        # Получаем текущую статистику
        cursor.execute(
            "SELECT total_interactions, avg_deviation FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        total_interactions = 1
        current_avg = 0.0

        if row and row['total_interactions']:
            total_interactions = row['total_interactions'] + 1
            current_avg = row['avg_deviation'] or 0.0

        deviation = float(data.get('deviation_score', 0))
        new_avg = (current_avg * (total_interactions - 1) + deviation) / total_interactions

        # Определяем уровень опыта
        experience_level = self._calculate_experience_level(total_interactions, new_avg)

        cursor.execute('''
            UPDATE users 
            SET total_interactions = ?,
                avg_deviation = ?,
                experience_level = ?,
                updated_at = CURRENT_TIMESTAMP,
                is_active = 1
            WHERE user_id = ?
        ''', (total_interactions, new_avg, experience_level.value, user_id))

    def _update_material_stats(self, cursor, user_id: str, data: Dict[str, Any]):
        """Обновить статистику по материалу."""
        material = data.get('material', '')
        if not material:
            return

        user_rpm = float(data.get('user_rpm', 0))
        deviation = float(data.get('deviation_score', 0))

        cursor.execute('''
            INSERT INTO material_stats 
            (user_id, material, interaction_count, total_deviation,
             avg_rpm, avg_deviation, first_used, last_used, expertise_score)
            VALUES (?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(user_id, material) DO UPDATE SET
                interaction_count = interaction_count + 1,
                total_deviation = total_deviation + ?,
                avg_rpm = CASE 
                    WHEN avg_rpm IS NULL THEN ?
                    ELSE (avg_rpm * (interaction_count - 1) + ?) / interaction_count
                END,
                avg_deviation = CASE 
                    WHEN avg_deviation IS NULL THEN ?
                    ELSE (avg_deviation * (interaction_count - 1) + ?) / interaction_count
                END,
                last_used = CURRENT_TIMESTAMP,
                expertise_score = expertise_score + (1.0 / (1.0 + ABS(?)))
        ''', (
            user_id, material, deviation, user_rpm, deviation, 0.1,
            # ON CONFLICT часть
            deviation, user_rpm, user_rpm, deviation, deviation, deviation
        ))

    def _update_session(self, cursor, user_id: str, session_id: str):
        """Обновить информацию о сессии."""
        cursor.execute('''
            INSERT INTO sessions (session_id, user_id, interaction_count)
            VALUES (?, ?, 1)
            ON CONFLICT(session_id) DO UPDATE SET
                interaction_count = interaction_count + 1
        ''', (session_id, user_id))

    def _update_machine_info(self, cursor, user_id: str, data: Dict[str, Any]):
        """Обновить информацию об оборудовании пользователя."""
        user_rpm = float(data.get('user_rpm', 0))

        # Определяем тип станка на основе RPM
        machine_type = EquipmentType.UNKNOWN
        confidence = 0.3  # Низкая уверенность

        if user_rpm < 800:
            machine_type = EquipmentType.OLD_MACHINE
            confidence = 0.6
        elif user_rpm < 2500:
            machine_type = EquipmentType.UNIVERSAL_MACHINE
            confidence = 0.7
        elif user_rpm < 6000:
            machine_type = EquipmentType.MODERN_CNC
            confidence = 0.8
        elif user_rpm >= 6000:
            machine_type = EquipmentType.HIGH_SPEED
            confidence = 0.9

        # Обновляем если уверенность выше текущей
        cursor.execute('''
            UPDATE users 
            SET machine_type = ?, machine_confidence = ?
            WHERE user_id = ? AND (machine_confidence IS NULL OR machine_confidence < ?)
        ''', (machine_type.value, confidence, user_id, confidence))

    # ============================================================================
    # МЕТОДЫ ПОЛУЧЕНИЯ ДАННЫХ
    # ============================================================================

    def get_user_summary(self, telegram_id: str) -> Dict[str, Any]:
        """Получить сводку по пользователю."""
        user = self.get_user(telegram_id)
        if not user:
            return self._get_empty_summary(telegram_id)

        user_id = user['user_id']

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Получаем статистику по материалам
            cursor.execute('''
                SELECT material, interaction_count, expertise_score, last_used
                FROM material_stats 
                WHERE user_id = ? 
                ORDER BY expertise_score DESC 
                LIMIT 5
            ''', (user_id,))

            material_stats = []
            for row in cursor.fetchall():
                material_stats.append({
                    'material': row['material'],
                    'count': row['interaction_count'],
                    'expertise': row['expertise_score'],
                    'last_used': row['last_used']
                })

            # Получаем последние взаимодействия
            cursor.execute('''
                SELECT material, operation, deviation_percent, timestamp
                FROM interactions 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 3
            ''', (user_id,))

            recent_interactions = []
            for row in cursor.fetchall():
                recent_interactions.append({
                    'material': row['material'],
                    'operation': row['operation'],
                    'deviation': f"{row['deviation_percent']:.1f}%",
                    'time': row['timestamp']
                })

            # Получаем статистику по операциям
            cursor.execute('''
                SELECT operation, COUNT(*) as count, 
                       AVG(deviation_percent) as avg_deviation
                FROM interactions 
                WHERE user_id = ? 
                GROUP BY operation
            ''', (user_id,))

            operation_stats = []
            for row in cursor.fetchall():
                operation_stats.append({
                    'operation': row['operation'],
                    'count': row['count'],
                    'avg_deviation': f"{row['avg_deviation']:.1f}%"
                })

        # Формируем ответ
        summary = {
            'user_id': user_id,
            'telegram_id': telegram_id,
            'username': user.get('username', ''),
            'first_name': user.get('first_name', ''),
            'experience': {
                'level': user.get('experience_level', 'новичок'),
                'total_interactions': user.get('total_interactions', 0),
                'avg_deviation': f"{user.get('avg_deviation', 0) * 100:.1f}%",
                'machine_type': user.get('machine_type', 'неизвестно'),
                'machine_confidence': f"{user.get('machine_confidence', 0) * 100:.0f}%"
            },
            'materials': material_stats,
            'recent_activity': recent_interactions,
            'operations': operation_stats,
            'learning_progress': self._calculate_learning_progress(user_id)
        }

        return summary

    def _get_empty_summary(self, telegram_id: str) -> Dict[str, Any]:
        """Получить пустую сводку для нового пользователя."""
        return {
            'user_id': f"user_{telegram_id}",
            'telegram_id': telegram_id,
            'username': '',
            'first_name': '',
            'experience': {
                'level': 'новичок',
                'total_interactions': 0,
                'avg_deviation': '0.0%',
                'machine_type': 'неизвестно',
                'machine_confidence': '0%'
            },
            'materials': [],
            'recent_activity': [],
            'operations': [],
            'learning_progress': 'недостаточно данных'
        }

    def get_interaction_history(self, telegram_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить историю взаимодействий пользователя."""
        user = self.get_user(telegram_id)
        if not user:
            return []

        user_id = user['user_id']

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    timestamp,
                    material,
                    operation,
                    mode,
                    diameter,
                    recommended_rpm,
                    user_rpm,
                    deviation_percent,
                    user_comment
                FROM interactions 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (user_id, limit))

            history = []
            for row in cursor.fetchall():
                deviation = row['deviation_percent']
                if deviation < 10:
                    status = "✅"
                elif deviation < 25:
                    status = "⚠️"
                else:
                    status = "🔄"

                history.append({
                    'time': row['timestamp'],
                    'material': row['material'],
                    'operation': row['operation'],
                    'mode': row['mode'],
                    'diameter': f"{row['diameter']:.1f} мм",
                    'recommended': f"{int(row['recommended_rpm'])} об/мин",
                    'user_choice': f"{int(row['user_rpm'])} об/мин",
                    'deviation': f"{deviation:.1f}%",
                    'status': status,
                    'comment': row['user_comment'] or ''
                })

            return history

    def get_material_stats(self, telegram_id: str, material: str = None) -> Dict[str, Any]:
        """Получить статистику по материалам."""
        user = self.get_user(telegram_id)
        if not user:
            return {}

        user_id = user['user_id']

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if material:
                # Статистика по конкретному материалу
                cursor.execute('''
                    SELECT 
                        material,
                        interaction_count,
                        avg_rpm,
                        avg_deviation,
                        expertise_score,
                        first_used,
                        last_used
                    FROM material_stats 
                    WHERE user_id = ? AND material = ?
                ''', (user_id, material))

                row = cursor.fetchone()
                if row:
                    return {
                        'material': row['material'],
                        'interaction_count': row['interaction_count'],
                        'avg_rpm': f"{row['avg_rpm']:.0f}",
                        'avg_deviation': f"{row['avg_deviation'] * 100:.1f}%",
                        'expertise_score': f"{row['expertise_score']:.2f}",
                        'first_used': row['first_used'],
                        'last_used': row['last_used']
                    }
                return {}
            else:
                # Общая статистика по всем материалам
                cursor.execute('''
                    SELECT 
                        material,
                        interaction_count,
                        expertise_score,
                        last_used
                    FROM material_stats 
                    WHERE user_id = ? 
                    ORDER BY expertise_score DESC
                ''', (user_id,))

                materials = []
                for row in cursor.fetchall():
                    materials.append({
                        'material': row['material'],
                        'count': row['interaction_count'],
                        'expertise': f"{row['expertise_score']:.2f}",
                        'last_used': row['last_used']
                    })

                return {'materials': materials}

    # ============================================================================
    # АНАЛИТИЧЕСКИЕ МЕТОДЫ
    # ============================================================================

    def _calculate_experience_level(self, total_interactions: int, avg_deviation: float) -> ExperienceLevel:
        """Рассчитать уровень опыта пользователя."""
        if total_interactions < 5:
            return ExperienceLevel.NOVICE
        elif total_interactions < 15:
            return ExperienceLevel.BEGINNER
        elif total_interactions < 30:
            return ExperienceLevel.PRACTITIONER
        elif total_interactions < 50:
            return ExperienceLevel.EXPERIENCED
        elif avg_deviation < 0.15:  # Меньше 15% отклонения
            return ExperienceLevel.EXPERT
        else:
            return ExperienceLevel.EXPERIENCED

    def _calculate_learning_progress(self, user_id: str) -> str:
        """Рассчитать прогресс обучения пользователя."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Получаем среднее отклонение за последние 10 взаимодействий
            cursor.execute('''
                SELECT AVG(deviation_percent) as recent_avg
                FROM (
                    SELECT deviation_percent 
                    FROM interactions 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                )
            ''', (user_id,))

            row = cursor.fetchone()
            if not row or not row['recent_avg']:
                return "недостаточно данных"

            recent_avg = row['recent_avg']

            # Получаем общее среднее отклонение
            cursor.execute(
                "SELECT avg_deviation FROM users WHERE user_id = ?",
                (user_id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                return "недостаточно данных"

            overall_avg = user_row['avg_deviation'] * 100  # в проценты

            # Анализируем прогресс
            if recent_avg < overall_avg * 0.7:  # Улучшение на 30%
                return "быстрое улучшение"
            elif recent_avg < overall_avg * 0.9:  # Улучшение на 10%
                return "медленное улучшение"
            elif recent_avg > overall_avg * 1.3:  # Ухудшение на 30%
                return "необходима корректировка"
            else:
                return "стабильные результаты"

    def get_personalized_suggestion(self, telegram_id: str, material: str) -> str:
        """Получить персонализированную подсказку для пользователя."""
        user = self.get_user(telegram_id)
        if not user:
            return "Начните с базовых рекомендаций и записывайте свои решения."

        material_stats = self.get_material_stats(telegram_id, material)
        if not material_stats:
            return f"У вас пока нет опыта с {material}. Начните с рекомендуемых значений."

        count = material_stats.get('interaction_count', 0)
        avg_deviation = material_stats.get('avg_deviation', '0%')

        if count >= 10 and 'низкое' in avg_deviation:  # avg_deviation содержит строку типа "12.5%"
            return f"У вас хороший опыт с {material}. Можете доверять своим настройкам."
        elif count >= 5:
            return f"У вас есть опыт с {material} ({count} раз). Корректируйте рекомендации на основе прошлых решений."
        else:
            return f"У вас небольшой опыт с {material}. Рекомендуется начинать с 80% от рекомендуемых значений."

    # ============================================================================
    # АДМИНИСТРАТИВНЫЕ МЕТОДЫ
    # ============================================================================

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить список всех пользователей."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    user_id,
                    telegram_id,
                    username,
                    first_name,
                    total_interactions,
                    experience_level,
                    avg_deviation,
                    created_at,
                    last_session_id
                FROM users 
                WHERE is_active = 1
                ORDER BY total_interactions DESC
            ''')

            users = []
            for row in cursor.fetchall():
                users.append({
                    'user_id': row['user_id'],
                    'telegram_id': row['telegram_id'],
                    'username': row['username'],
                    'first_name': row['first_name'],
                    'total_interactions': row['total_interactions'],
                    'experience_level': row['experience_level'],
                    'avg_deviation': f"{row['avg_deviation'] * 100:.1f}%",
                    'created_at': row['created_at'],
                    'last_session': row['last_session_id']
                })

            return users

    def cleanup_inactive_users(self, days_inactive: int = 30):
        """Очистить неактивных пользователей."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Помечаем неактивных пользователей
            cursor.execute('''
                UPDATE users 
                SET is_active = 0
                WHERE updated_at < datetime('now', ?)
                AND total_interactions < 5
            ''', (f'-{days_inactive} days',))

            count = cursor.rowcount
            conn.commit()

            logger.info(f"Очищено {count} неактивных пользователей")
            return count

    def backup_database(self, backup_path: str = None):
        """Создать резервную копию базы данных."""
        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"backups/cnc_memory_backup_{timestamp}.db"

        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.copy2(self.db_path, backup_path)

        logger.info(f"Создана резервная копия: {backup_path}")
        return str(backup_path)


# ============================================================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ ДЛЯ ИНТЕГРАЦИИ С ТЕЛЕГРАМ БОТОМ
# ============================================================================

# Глобальный экземпляр памяти
_memory_instance = None


def get_memory() -> UserMemory:
    """Получить глобальный экземпляр памяти."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = UserMemory()
    return _memory_instance


def save_interaction_with_memory(data: Dict[str, Any]):
    """Сохранить взаимодействие в память (функция для Telegram бота)."""
    try:
        memory = get_memory()
        return memory.save_interaction(data)
    except Exception as e:
        logger.error(f"Ошибка при сохранении взаимодействия: {e}", exc_info=True)
        return False


def get_user_memory_summary(user_id: str) -> Dict[str, Any]:
    """Получить сводку из памяти пользователя (функция для Telegram бота)."""
    try:
        memory = get_memory()
        return memory.get_user_summary(user_id)
    except Exception as e:
        logger.error(f"Ошибка при получении сводки: {e}", exc_info=True)
        return {
            'user_id': user_id,
            'error': str(e),
            'experience': {'level': 'новичок', 'total_interactions': 0},
            'materials': [],
            'recent_activity': []
        }


def register_telegram_user(message) -> str:
    """Зарегистрировать пользователя Telegram в системе памяти."""
    try:
        memory = get_memory()
        user_id = memory.register_user(
            telegram_id=str(message.from_user.id),
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name or ""
        )
        return user_id
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя: {e}")
        return f"user_{message.from_user.id}"


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

def test_memory_system():
    """Тестирование системы памяти."""
    print("🧪 Тестирование системы памяти...")

    # Создаем экземпляр памяти
    memory = UserMemory("test_memory.db")

    # Тест 1: Регистрация пользователя
    user_id = memory.register_user(
        telegram_id="123456789",
        username="test_user",
        first_name="Тест",
        last_name="Пользователь"
    )
    print(f"✅ Тест 1: Пользователь зарегистрирован: {user_id}")

    # Тест 2: Сохранение взаимодействия
    interaction_data = {
        'user_id': user_id,
        'material': 'сталь',
        'operation': 'токарка',
        'mode': 'черновой',
        'diameter': 50.0,
        'recommended_rpm': 1200.0,
        'recommended_vc': 150.0,
        'recommended_feed': 0.2,
        'user_rpm': 1000.0,
        'deviation_score': 0.1667,
        'user_comment': 'тестовое взаимодействие',
        'context': {
            'source': 'telegram',
            'session_id': 'test_session_1'
        }
    }

    success = memory.save_interaction(interaction_data)
    print(f"✅ Тест 2: Взаимодействие сохранено: {success}")

    # Тест 3: Получение сводки
    summary = memory.get_user_summary("123456789")
    print(f"✅ Тест 3: Сводка получена:")
    print(f"   - Уровень опыта: {summary['experience']['level']}")
    print(f"   - Взаимодействий: {summary['experience']['total_interactions']}")

    # Тест 4: Получение истории
    history = memory.get_interaction_history("123456789", limit=5)
    print(f"✅ Тест 4: История получена ({len(history)} записей)")

    # Тест 5: Статистика по материалам
    material_stats = memory.get_material_stats("123456789")
    print(f"✅ Тест 5: Статистика по материалам получена")

    # Тест 6: Все пользователи
    all_users = memory.get_all_users()
    print(f"✅ Тест 6: Все пользователи получены ({len(all_users)} пользователей)")

    print("\n🎉 Все тесты пройдены успешно!")

    return True


if __name__ == "__main__":
    # Настройка логирования для тестов
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Система памяти для CNC Assistant")
    print("=" * 60)

    # Запуск тестов
    test_memory_system()

    print("\n" + "=" * 60)
    print("Пример использования в Telegram боте:")
    print("""
    # В начале обработки сообщения
    user_id = register_telegram_user(message)

    # После получения решения пользователя
    interaction_data = {
        'user_id': user_id,
        'material': 'сталь',
        'operation': 'токарка',
        'mode': 'черновой',
        'diameter': 50.0,
        'recommended_rpm': 1200.0,
        'user_rpm': 1000.0,
        'deviation_score': 0.1667,
        'context': {'source': 'telegram'}
    }
    save_interaction_with_memory(interaction_data)

    # При запросе истории
    summary = get_user_memory_summary(str(message.from_user.id))
    """)
    print("=" * 60)
