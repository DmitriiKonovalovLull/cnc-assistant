"""
Миграции базы данных.
Добавляет недостающие столбцы в существующие таблицы.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def check_column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """Проверить, существует ли столбец в таблице."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_add_operation_chain_json(db_path: str = "app/storage/cnc.db"):
    """
    Миграция: добавить столбец operation_chain_json в таблицу user_decisions.
    
    Args:
        db_path: Путь к базе данных (может быть относительным или абсолютным)
    """
    db_file = Path(db_path)
    if not db_file.is_absolute():
        # Если путь относительный, делаем его относительно корня проекта
        project_root = Path(__file__).parent.parent.parent
        db_file = project_root / db_path
    
    if not db_file.exists():
        logger.warning(f"Database file not found: {db_file}. Skipping migration.")
        return
    
    try:
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        # Проверяем, существует ли столбец
        if not check_column_exists(cursor, 'user_decisions', 'operation_chain_json'):
            logger.info("Adding column 'operation_chain_json' to table 'user_decisions'")
            cursor.execute('''
                ALTER TABLE user_decisions 
                ADD COLUMN operation_chain_json TEXT DEFAULT '[]'
            ''')
            conn.commit()
            logger.info("Migration completed: operation_chain_json added")
        else:
            logger.info("Column 'operation_chain_json' already exists. Skipping migration.")
        
        conn.close()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_experience_profiles_columns(db_path: str = "app/storage/cnc.db"):
    """Добавить недостающие столбцы в experience_profiles (chain_operation_count и др.)."""
    db_file = Path(db_path)
    if not db_file.is_absolute():
        project_root = Path(__file__).parent.parent.parent
        db_file = project_root / db_path
    if not db_file.exists():
        logger.warning(f"Database file not found: {db_file}. Skipping migration.")
        return
    columns_to_add = [
        ("chain_operation_count", "INTEGER DEFAULT 0"),
        ("avg_chain_length", "REAL DEFAULT 1.0"),
        ("avg_rpm_coeff", "REAL DEFAULT 1.0"),
        ("avg_feed_coeff", "REAL DEFAULT 1.0"),
        ("avg_ap_coeff", "REAL DEFAULT 1.0"),
        ("material_adaptation_score", "REAL DEFAULT 0.0"),
        ("diameter_adaptation_score", "REAL DEFAULT 0.0"),
        ("operation_adaptation_score", "REAL DEFAULT 0.0"),
        ("chain_adaptation_score", "REAL DEFAULT 0.0"),
        ("risk_tolerance", "REAL DEFAULT 0.5"),
        ("preferred_aggressiveness", "REAL DEFAULT 0.5"),
        ("preferred_chain_pattern_json", "TEXT DEFAULT '{}'"),
    ]
    try:
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        if not _table_exists(cursor, "experience_profiles"):
            conn.close()
            return
        for col_name, col_def in columns_to_add:
            if not check_column_exists(cursor, "experience_profiles", col_name):
                logger.info("Adding column '%s' to experience_profiles", col_name)
                cursor.execute(
                    f"ALTER TABLE experience_profiles ADD COLUMN {col_name} {col_def}"
                )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Migration experience_profiles failed: %s", e)
        raise


def run_all_migrations(db_path: str = "app/storage/cnc.db"):
    """
    Запустить все миграции.
    
    Args:
        db_path: Путь к базе данных (может быть относительным или абсолютным)
    """
    logger.info("Running database migrations...")
    
    try:
        migrate_add_operation_chain_json(db_path)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    try:
        migrate_experience_profiles_columns(db_path)
    except Exception as e:
        logger.error(f"Migration experience_profiles failed: {e}")
        raise
    logger.info("All migrations completed")


if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app/storage/cnc.db"
    logging.basicConfig(level=logging.INFO)
    
    run_all_migrations(db_path)
    print("✅ Migrations completed successfully")
