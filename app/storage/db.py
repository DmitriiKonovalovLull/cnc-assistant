"""
Модуль для работы с базой данных.
SQLite с поддержкой JSON полей.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager

# Импортируем наши модели
from app.domain.models import (
    UserDecisionRecord, ExperienceProfile, MachineSpecs,
    MaterialData, ToolData, GeometryData, OperationData,
    BotRecommendation, UserActual, OperationResult,
    MachineType, MaterialType, ToolType, OperationType,
    ComparisonChoice, ResultType, ExperienceLevel
)

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных."""

    def __init__(self, db_path: str = "storage/cnc_assistant.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для соединения с БД."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Возвращать строки как словари
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    async def initialize(self):
        """Инициализация базы данных (создание таблиц)."""
        logger.info(f"Initializing database at {self.db_path}")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # ========== ОСНОВНЫЕ ТАБЛИЦЫ ==========

            # Таблица пользователей
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_decisions INTEGER DEFAULT 0,
                experience_level TEXT DEFAULT 'unknown',
                preferences_json TEXT DEFAULT '{}',
                metadata_json TEXT DEFAULT '{}'
            )
            ''')

            # Таблица решений (основная)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                record_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,

                -- Контекст (JSON поля)
                machine_json TEXT NOT NULL,
                material_json TEXT NOT NULL,
                tool_json TEXT NOT NULL,
                geometry_json TEXT NOT NULL,
                operation_json TEXT NOT NULL,

                -- Рекомендации
                bot_recommendation_json TEXT NOT NULL,
                user_actual_json TEXT NOT NULL,

                -- Результат
                operation_result_json TEXT,

                -- Метаданные
                experience_level TEXT,
                was_decision_adaptive BOOLEAN DEFAULT FALSE,

                -- Для поиска
                material_type TEXT,
                operation_type TEXT,
                tool_type TEXT,
                diameter_start REAL,
                diameter_end REAL,

                -- Статистика (вычисляемые поля)
                diff_rpm_coeff REAL,
                diff_feed_coeff REAL,
                diff_ap_coeff REAL,
                variance_score REAL,

                -- Индексы
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')

            # Таблица для сессий (группировка решений)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                total_decisions INTEGER DEFAULT 0,
                session_context_json TEXT DEFAULT '{}',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')

            # Таблица для обратной связи (пост-обработка)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Обратная связь от оператора
                actual_result_type TEXT,
                actual_result_details TEXT,
                actual_tool_life_minutes REAL,
                actual_machining_time_minutes REAL,
                issues_encountered_json TEXT DEFAULT '[]',
                operator_rating INTEGER, -- 1-5
                operator_comment TEXT,

                -- Системная оценка
                success_score REAL, -- 0-1
                adaptation_validation BOOLEAN, -- подтвердилась ли адаптивность
                lessons_learned_json TEXT DEFAULT '{}',

                FOREIGN KEY (record_id) REFERENCES decisions (record_id)
            )
            ''')

            # ========== СПРАВОЧНИКИ ==========

            # Материалы (кэш нормализованных значений)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS material_reference (
                material_id TEXT PRIMARY KEY,
                normalized_name TEXT NOT NULL,
                material_type TEXT NOT NULL,
                hardness_range_min REAL,
                hardness_range_max REAL,
                tensile_strength_min REAL,
                tensile_strength_max REAL,
                recommended_vc_min REAL,
                recommended_vc_max REAL,
                typical_feed_range TEXT, -- JSON
                typical_ap_range TEXT, -- JSON
                source TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Инструменты
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tool_reference (
                tool_id TEXT PRIMARY KEY,
                tool_type TEXT NOT NULL,
                insert_material TEXT NOT NULL,
                insert_grade TEXT,
                typical_radius_mm REAL,
                recommended_vc_multiplier REAL DEFAULT 1.0,
                recommended_feed_multiplier REAL DEFAULT 1.0,
                max_depth_of_cut_mm REAL,
                source TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # ========== ИНДЕКСЫ ==========

            # Основные индексы для быстрого поиска
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_decisions_user_timestamp 
            ON decisions (user_id, timestamp DESC)
            ''')

            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_decisions_material_operation 
            ON decisions (material_type, operation_type)
            ''')

            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_decisions_diameter 
            ON decisions (diameter_start, diameter_end)
            ''')

            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_decisions_adaptive 
            ON decisions (was_decision_adaptive)
            ''')

            # Индекс для обратной связи
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_feedback_record 
            ON feedback (record_id)
            ''')

            logger.info("Database tables created successfully")

    async def save_decision(self, decision: UserDecisionRecord) -> str:
        """
        Сохранить решение оператора в базу данных.

        Args:
            decision: Запись решения

        Returns:
            record_id: ID сохраненной записи
        """
        logger.info(f"Saving decision {decision.record_id} for user {decision.user_id}")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Обновляем/создаем пользователя
            cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, first_seen) 
            VALUES (?, CURRENT_TIMESTAMP)
            ''', (decision.user_id,))

            cursor.execute('''
            UPDATE users 
            SET last_seen = CURRENT_TIMESTAMP,
                total_decisions = total_decisions + 1
            WHERE user_id = ?
            ''', (decision.user_id,))

            # 2. Сохраняем решение
            cursor.execute('''
            INSERT INTO decisions (
                record_id, user_id, timestamp,
                machine_json, material_json, tool_json, 
                geometry_json, operation_json,
                bot_recommendation_json, user_actual_json,
                operation_result_json,
                experience_level, was_decision_adaptive,
                material_type, operation_type, tool_type,
                diameter_start, diameter_end,
                diff_rpm_coeff, diff_feed_coeff, diff_ap_coeff,
                variance_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                decision.record_id,
                decision.user_id,
                decision.timestamp.isoformat(),
                decision.machine.to_json(),
                decision.material.to_json(),
                decision.tool.to_json(),
                decision.geometry.to_json(),
                decision.operation.to_json(),
                decision.bot_recommendation.to_json(),
                decision.user_actual.to_json(),
                decision.operation_result.to_json() if decision.operation_result else None,
                decision.experience_level.value,
                decision.was_decision_adaptive,
                decision.material.material_type.value,
                decision.operation.operation_type.value,
                decision.tool.tool_type.value,
                decision.geometry.diameter_start_mm,
                decision.geometry.diameter_end_mm,
                decision.difference_coeff_rpm,
                decision.difference_coeff_feed,
                decision.difference_coeff_ap,
                decision.variance_adaptation_score
            ))

            return decision.record_id

    async def save_feedback(self, record_id: str, feedback_data: Dict[str, Any]) -> str:
        """
        Сохранить обратную связь по выполненной операции.

        Args:
            record_id: ID записи решения
            feedback_data: Данные обратной связи

        Returns:
            feedback_id: ID сохраненной обратной связи
        """
        import uuid

        feedback_id = f"feedback_{uuid.uuid4().hex[:8]}"

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO feedback (
                feedback_id, record_id,
                actual_result_type, actual_result_details,
                actual_tool_life_minutes, actual_machining_time_minutes,
                issues_encountered_json, operator_rating, operator_comment,
                success_score, adaptation_validation, lessons_learned_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                feedback_id,
                record_id,
                feedback_data.get('actual_result_type'),
                feedback_data.get('actual_result_details'),
                feedback_data.get('actual_tool_life_minutes'),
                feedback_data.get('actual_machining_time_minutes'),
                json.dumps(feedback_data.get('issues_encountered', [])),
                feedback_data.get('operator_rating'),
                feedback_data.get('operator_comment'),
                feedback_data.get('success_score'),
                feedback_data.get('adaptation_validation'),
                json.dumps(feedback_data.get('lessons_learned', {}))
            ))

            return feedback_id

    async def get_user_decisions(
            self,
            user_id: str,
            limit: int = 100,
            offset: int = 0
    ) -> List[UserDecisionRecord]:
        """
        Получить решения пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            offset: Смещение

        Returns:
            Список записей решений
        """
        decisions = []

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM decisions 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))

            for row in cursor.fetchall():
                try:
                    decision = UserDecisionRecord.from_dict({
                        'record_id': row['record_id'],
                        'user_id': row['user_id'],
                        'timestamp': datetime.fromisoformat(row['timestamp']),
                        'machine': json.loads(row['machine_json']),
                        'material': json.loads(row['material_json']),
                        'tool': json.loads(row['tool_json']),
                        'geometry': json.loads(row['geometry_json']),
                        'operation': json.loads(row['operation_json']),
                        'bot_recommendation': json.loads(row['bot_recommendation_json']),
                        'user_actual': json.loads(row['user_actual_json']),
                        'operation_result': json.loads(row['operation_result_json']) if row[
                            'operation_result_json'] else None,
                        'experience_level': row['experience_level'],
                        'was_decision_adaptive': bool(row['was_decision_adaptive'])
                    })
                    decisions.append(decision)
                except Exception as e:
                    logger.error(f"Error parsing decision {row['record_id']}: {e}")

        return decisions

    async def get_similar_decisions(
            self,
            material_type: str,
            operation_type: str,
            diameter_range: Tuple[float, float],
            limit: int = 50
    ) -> List[UserDecisionRecord]:
        """
        Найти похожие решения по параметрам.

        Args:
            material_type: Тип материала
            operation_type: Тип операции
            diameter_range: Диапазон диаметров (min, max)
            limit: Максимальное количество

        Returns:
            Список похожих решений
        """
        decisions = []

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM decisions 
            WHERE material_type = ? 
            AND operation_type = ?
            AND diameter_start BETWEEN ? AND ?
            ORDER BY timestamp DESC 
            LIMIT ?
            ''', (material_type, operation_type, diameter_range[0], diameter_range[1], limit))

            for row in cursor.fetchall():
                try:
                    decision = UserDecisionRecord.from_dict({
                        'record_id': row['record_id'],
                        'user_id': row['user_id'],
                        'timestamp': datetime.fromisoformat(row['timestamp']),
                        'machine': json.loads(row['machine_json']),
                        'material': json.loads(row['material_json']),
                        'tool': json.loads(row['tool_json']),
                        'geometry': json.loads(row['geometry_json']),
                        'operation': json.loads(row['operation_json']),
                        'bot_recommendation': json.loads(row['bot_recommendation_json']),
                        'user_actual': json.loads(row['user_actual_json']),
                        'experience_level': row['experience_level'],
                        'was_decision_adaptive': bool(row['was_decision_adaptive'])
                    })
                    decisions.append(decision)
                except Exception as e:
                    logger.error(f"Error parsing similar decision: {e}")

        return decisions

    async def get_experience_profile(self, user_id: str) -> Optional[ExperienceProfile]:
        """
        Получить или создать профиль опыта пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Профиль опыта или None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Получаем статистику по решениям пользователя
            cursor.execute('''
            SELECT 
                COUNT(*) as total_decisions,
                SUM(CASE WHEN was_decision_adaptive THEN 1 ELSE 0 END) as adaptive_decisions,
                AVG(diff_rpm_coeff) as avg_rpm_coeff,
                AVG(diff_feed_coeff) as avg_feed_coeff,
                AVG(diff_ap_coeff) as avg_ap_coeff,
                AVG(variance_score) as avg_variance_score
            FROM decisions 
            WHERE user_id = ?
            ''', (user_id,))

            stats = cursor.fetchone()

            if not stats or stats['total_decisions'] == 0:
                # Если нет решений, возвращаем базовый профиль
                return ExperienceProfile(user_id=user_id)

            # Получаем адаптивность по разным материалам
            cursor.execute('''
            SELECT 
                material_type,
                COUNT(*) as count,
                AVG(variance_score) as avg_score
            FROM decisions 
            WHERE user_id = ? AND was_decision_adaptive = TRUE
            GROUP BY material_type
            ''', (user_id,))

            material_scores = cursor.fetchall()
            material_adaptation = sum(row['avg_score'] for row in material_scores) / max(len(material_scores), 1)

            # Создаем профиль
            profile = ExperienceProfile(
                user_id=user_id,
                total_decisions=stats['total_decisions'],
                adaptive_decisions=stats['adaptive_decisions'],
                avg_rpm_coeff=stats['avg_rpm_coeff'] or 1.0,
                avg_feed_coeff=stats['avg_feed_coeff'] or 1.0,
                avg_ap_coeff=stats['avg_ap_coeff'] or 1.0,
                material_adaptation_score=material_adaptation,
                diameter_adaptation_score=stats['avg_variance_score'] or 0.0,
                operation_adaptation_score=stats['avg_variance_score'] or 0.0
            )

            return profile

    async def export_training_data(self, output_path: Path) -> int:
        """
        Экспортировать данные для обучения в формате JSONL.

        Args:
            output_path: Путь для сохранения

        Returns:
            Количество экспортированных записей
        """
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Выбираем только завершенные решения с обратной связью
            cursor.execute('''
            SELECT d.*, f.* 
            FROM decisions d
            LEFT JOIN feedback f ON d.record_id = f.record_id
            WHERE f.feedback_id IS NOT NULL
            ORDER BY d.timestamp DESC
            ''')

            records = cursor.fetchall()

            training_data = []
            for row in records:
                try:
                    # Формируем запись для обучения
                    training_record = {
                        'input': {
                            'material': row['material_type'],
                            'operation': row['operation_type'],
                            'diameter_start': row['diameter_start'],
                            'diameter_end': row['diameter_end']
                        },
                        'context': {
                            'machine': json.loads(row['machine_json']),
                            'tool': json.loads(row['tool_json'])
                        },
                        'bot_recommendation': json.loads(row['bot_recommendation_json']),
                        'user_decision': json.loads(row['user_actual_json']),
                        'feedback': {
                            'actual_result': row['actual_result_type'],
                            'success_score': row['success_score']
                        } if row['actual_result_type'] else None,
                        'metadata': {
                            'record_id': row['record_id'],
                            'user_id': row['user_id'],
                            'timestamp': row['timestamp'],
                            'was_adaptive': bool(row['was_decision_adaptive'])
                        }
                    }
                    training_data.append(training_record)
                except Exception as e:
                    logger.error(f"Error processing record {row['record_id']}: {e}")

            # Сохраняем в JSONL
            with open(output_path, 'w', encoding='utf-8') as f:
                for record in training_data:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')

            logger.info(f"Exported {len(training_data)} records to {output_path}")
            return len(training_data)

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику по базе данных.

        Returns:
            Словарь со статистикой
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Основная статистика
            cursor.execute('SELECT COUNT(*) as total FROM decisions')
            stats['total_decisions'] = cursor.fetchone()['total']

            cursor.execute('SELECT COUNT(DISTINCT user_id) as total FROM users')
            stats['total_users'] = cursor.fetchone()['total']

            cursor.execute('SELECT COUNT(*) as total FROM feedback')
            stats['total_feedback'] = cursor.fetchone()['total']

            # Статистика по материалам
            cursor.execute('''
            SELECT material_type, COUNT(*) as count 
            FROM decisions 
            GROUP BY material_type 
            ORDER BY count DESC
            ''')
            stats['by_material'] = dict(cursor.fetchall())

            # Статистика по операциям
            cursor.execute('''
            SELECT operation_type, COUNT(*) as count 
            FROM decisions 
            GROUP BY operation_type 
            ORDER BY count DESC
            ''')
            stats['by_operation'] = dict(cursor.fetchall())

            # Средняя адаптивность
            cursor.execute('SELECT AVG(variance_score) as avg FROM decisions')
            stats['avg_adaptation_score'] = cursor.fetchone()['avg'] or 0.0

            # Количество адаптивных решений
            cursor.execute('SELECT COUNT(*) as count FROM decisions WHERE was_decision_adaptive = TRUE')
            stats['adaptive_decisions'] = cursor.fetchone()['count']

            return stats

    async def close(self):
        """Закрыть соединения с базой данных."""
        logger.info("Database connection closed")


# Утилитарные функции для обратной совместимости
def init_database_legacy(db_path: str = "storage/cnc.db"):
    """
    Функция для обратной совместимости.
    Можно удалить после миграции на новую схему.
    """
    db = Database(db_path)
    asyncio.run(db.initialize())
    print(f"База данных инициализирована: {db_path}")


if __name__ == "__main__":
    # Тестирование базы данных
    import asyncio


    async def test_db():
        db = Database("test.db")
        await db.initialize()

        # Создаем тестовую запись
        from app.domain.models import create_sample_decision
        test_decision = create_sample_decision()

        # Сохраняем
        record_id = await db.save_decision(test_decision)
        print(f"Saved decision: {record_id}")

        # Получаем статистику
        stats = await db.get_statistics()
        print(f"Statistics: {stats}")

        # Экспортируем данные
        await db.export_training_data(Path("test_training.jsonl"))

        await db.close()


    asyncio.run(test_db())