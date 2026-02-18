#!/usr/bin/env python
"""
Управление базой стандартов.
Команда для проверки обновлений, загрузки и проверки целостности.
"""

import sys
import argparse
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_db():
    """Настроить подключение к БД."""
    # TODO: Интегрировать с существующей БД проекта
    # Пока заглушка
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # Используем SQLite для примера (в production - PostgreSQL)
        db_path = Path("standards_cache/standards.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        
        # Создаем таблицы
        from standards.database.models import Base
        Base.metadata.create_all(engine)
        
        return Session()
    
    except Exception as e:
        logger.error(f"Failed to setup DB: {e}", exc_info=True)
        return None


def cmd_update(args):
    """Команда обновления стандартов."""
    print("=== STANDARD UPDATE ===\n")
    
    db_session = setup_db()
    if not db_session:
        print("❌ Failed to connect to database")
        return 1
    
    try:
        from standards.manager.standard_manager import StandardManager
        from standards.integrity.update_checker import UpdateChecker
        
        # Создаем менеджер
        manager = StandardManager()
        
        # Создаем проверщик обновлений
        checker = UpdateChecker(db_session, manager)
        
        # Проверяем обновления
        results = checker.check_updates(force=args.force)
        
        if 'error' in results:
            print(f"❌ Error: {results['error']}")
            return 1
        
        # Выводим результаты по семействам
        family_results = {}
        for detail in results.get('details', []):
            standard = detail.get('standard', '')
            if not standard:
                continue
            
            # Определяем семейство из кода
            family = standard.split()[0] if ' ' in standard else 'UNKNOWN'
            
            if family not in family_results:
                family_results[family] = {'checked': 0, 'updated': 0}
            
            family_results[family]['checked'] += 1
            if detail.get('updated'):
                family_results[family]['updated'] += 1
        
        # Выводим статистику
        for family, stats in family_results.items():
            updated_str = f", {stats['updated']} updated" if stats['updated'] > 0 else ""
            print(f"{family}: {stats['checked']} checked{updated_str}")
        
        print(f"\nTotal: {results['checked']} checked, {results['updated']} updated")
        
        # Проверяем целостность
        integrity = manager.verify_integrity()
        if integrity.get('all_ok'):
            print("\nIntegrity: ✅ OK")
        else:
            print("\nIntegrity: ⚠️ ISSUES FOUND")
            if integrity.get('missing_files'):
                print(f"Missing: {len(integrity['missing_files'])} files")
            if integrity.get('corrupted_files'):
                print(f"Corrupted: {len(integrity['corrupted_files'])} files")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error in update command: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1


def cmd_status(args):
    """Команда проверки статуса базы."""
    print("=== STANDARD SYSTEM CHECK ===\n")
    
    try:
        from standards.manager.standard_manager import StandardManager
        
        manager = StandardManager()
        message = manager.format_status_message()
        
        print(message)
        
        return 0
    
    except Exception as e:
        logger.error(f"Error in status command: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1


def cmd_mark_suspicious(args):
    """Пометить стандарт как подозрительный."""
    db_session = setup_db()
    if not db_session:
        print("❌ Failed to connect to database")
        return 1
    
    try:
        from standards.integrity.update_checker import UpdateChecker
        from standards.manager.standard_manager import StandardManager
        
        manager = StandardManager()
        checker = UpdateChecker(db_session, manager)
        
        # Ищем стандарт по коду
        from standards.database.models import Standard
        
        standard = db_session.query(Standard).filter(
            Standard.full_code == args.code
        ).first()
        
        if not standard:
            print(f"❌ Standard not found: {args.code}")
            return 1
        
        if checker.mark_as_suspicious(str(standard.id)):
            print(f"✅ Marked {args.code} as suspicious")
            return 0
        else:
            print(f"❌ Failed to mark {args.code}")
            return 1
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Управление базой стандартов")
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Команда update
    update_parser = subparsers.add_parser('update', help='Проверить обновления стандартов')
    update_parser.add_argument('--force', action='store_true', help='Принудительная проверка всех')
    update_parser.set_defaults(func=cmd_update)
    
    # Команда status
    status_parser = subparsers.add_parser('status', help='Проверить статус базы стандартов')
    status_parser.set_defaults(func=cmd_status)
    
    # Команда mark-suspicious
    mark_parser = subparsers.add_parser('mark-suspicious', help='Пометить стандарт как подозрительный')
    mark_parser.add_argument('code', help='Код стандарта (например "ОСТ 33056-80")')
    mark_parser.set_defaults(func=cmd_mark_suspicious)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
