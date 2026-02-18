#!/usr/bin/env python
"""
CLI для управления базой стандартов.
Команды: check, integrity, import, list
"""

import sys
import argparse
import logging
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.standards.manager import StandardManager
from app.standards.repository import StandardRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_session() -> Session:
    """Получить сессию БД."""
    return SessionLocal()


def cmd_check(args):
    """Команда проверки обновлений."""
    print("=== STANDARD CHECK ===\n")
    
    db = get_db_session()
    try:
        manager = StandardManager(db)
        results = manager.check_updates(force=args.force)
        
        # Форматируем вывод по семействам
        family_results = {}
        for detail in results.get('details', []):
            standard = detail.get('standard', '')
            if not standard:
                continue
            
            # Определяем семейство
            family = standard.split()[0] if ' ' in standard else 'UNKNOWN'
            
            if family not in family_results:
                family_results[family] = {'checked': 0, 'updated': 0, 'status': []}
            
            family_results[family]['checked'] += 1
            status = detail.get('status', 'unknown')
            family_results[family]['status'].append(f"{standard}: {status}")
        
        # Выводим результаты
        for family, stats in family_results.items():
            updated_count = sum(1 for s in stats['status'] if 'updated' in s.lower())
            status_icon = "✅" if updated_count == 0 else "⚠️"
            print(f"{status_icon} {family}: {stats['checked']} checked")
            if updated_count > 0:
                print(f"   {updated_count} updates available")
        
        print(f"\nTotal: {results['checked']} checked, {results['updated']} updated")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error in check: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1
    finally:
        db.close()


def cmd_integrity(args):
    """Команда проверки целостности."""
    print("=== INTEGRITY CHECK ===\n")
    
    db = get_db_session()
    try:
        manager = StandardManager(db)
        results = manager.verify_integrity()
        
        print(f"Total standards: {results['total_standards']}")
        print(f"Missing files: {results['missing_files']}")
        print(f"Corrupted files: {results['corrupted_files']}")
        
        if results['all_ok']:
            print("\nIntegrity: ✅ PASSED")
        else:
            print("\nIntegrity: ❌ FAILED")
            if results['details']:
                print("\nDetails:")
                for detail in results['details'][:10]:  # Показываем первые 10
                    print(f"  - {detail.get('standard', 'unknown')}: {detail.get('issue', 'unknown')}")
        
        return 0 if results['all_ok'] else 1
    
    except Exception as e:
        logger.error(f"Error in integrity: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1
    finally:
        db.close()


def cmd_import(args):
    """Команда импорта стандарта из файла."""
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return 1
    
    if not file_path.suffix.lower() == '.pdf':
        print(f"❌ File must be PDF: {file_path}")
        return 1
    
    print(f"Importing standard from: {file_path.name}\n")
    
    db = get_db_session()
    try:
        manager = StandardManager(db)
        
        # Парсим параметры
        family = args.family.upper()
        code = args.code
        full_code = args.full_code or f"{family} {code}"
        
        result = manager.upload_standard(
            file_path=file_path,
            family=family,
            code=code,
            full_code=full_code,
            title=args.title,
            country=args.country,
            revision=args.revision
        )
        
        if result['success']:
            print(f"✅ Successfully imported: {full_code}")
            print(f"   Standard ID: {result['standard_id']}")
            print(f"   Version hash: {result['version_hash'][:16]}...")
            return 0
        else:
            print(f"❌ Import failed: {result['message']}")
            return 1
    
    except Exception as e:
        logger.error(f"Error in import: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1
    finally:
        db.close()


def cmd_list(args):
    """Команда списка стандартов."""
    db = get_db_session()
    try:
        repository = StandardRepository(db)
        
        if args.family:
            standards = repository.get_by_family(args.family.upper())
        else:
            standards = repository.get_all(limit=args.limit)
        
        print(f"=== STANDARDS LIST ({len(standards)} standards) ===\n")
        
        for standard in standards:
            status_icon = "⚠️" if standard.needs_review else "✅"
            print(f"{status_icon} {standard.family} {standard.code} - {standard.full_code}")
            if standard.title:
                print(f"   {standard.title}")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error in list: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        return 1
    finally:
        db.close()


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(description="Управление базой стандартов")
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Команда check
    check_parser = subparsers.add_parser('check', help='Проверить обновления стандартов')
    check_parser.add_argument('--force', action='store_true', help='Принудительная проверка всех')
    check_parser.set_defaults(func=cmd_check)
    
    # Команда integrity
    integrity_parser = subparsers.add_parser('integrity', help='Проверить целостность базы')
    integrity_parser.set_defaults(func=cmd_integrity)
    
    # Команда import
    import_parser = subparsers.add_parser('import', help='Импортировать стандарт из PDF')
    import_parser.add_argument('file', help='Путь к PDF файлу')
    import_parser.add_argument('--family', required=True, help='Семейство стандарта (ISO, DIN, GOST, OST...)')
    import_parser.add_argument('--code', required=True, help='Код стандарта (например, 33056-80)')
    import_parser.add_argument('--full-code', help='Полный код (например, ОСТ 1 33056-80)')
    import_parser.add_argument('--title', help='Название стандарта')
    import_parser.add_argument('--country', help='Страна/организация')
    import_parser.add_argument('--revision', help='Ревизия')
    import_parser.set_defaults(func=cmd_import)
    
    # Команда list
    list_parser = subparsers.add_parser('list', help='Список стандартов')
    list_parser.add_argument('--family', help='Фильтр по семейству')
    list_parser.add_argument('--limit', type=int, default=100, help='Максимум записей')
    list_parser.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
