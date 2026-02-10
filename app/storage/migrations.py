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


def run_all_migrations(db_path: str = "app/storage/cnc.db"):
    """
    Запустить все миграции.
    
    Args:
        db_path: Путь к базе данных (может быть относительным или абсолютным)
    """
    logger.info("Running database migrations...")
    
    # Миграция 1: operation_chain_json
    try:
        migrate_add_operation_chain_json(db_path)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    
    logger.info("All migrations completed")


if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app/storage/cnc.db"
    logging.basicConfig(level=logging.INFO)
    
    run_all_migrations(db_path)
    print("✅ Migrations completed successfully")
