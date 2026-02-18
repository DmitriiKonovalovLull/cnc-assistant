"""
CLI команда для обновления базы стандартов.
"""

import argparse
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from standards.downloader.standard_downloader import StandardDownloader, download_all_standards
from standards.loader import load_all_standards

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def update_standards_command(args):
    """Команда обновления стандартов."""
    print("=" * 60)
    print("  Обновление базы стандартов")
    print("=" * 60)
    
    downloader = StandardDownloader()
    
    if args.download:
        print("\n📥 Скачивание стандартов...")
        results = download_all_standards()
        
        print(f"\n✅ Скачано: {len(results['downloaded'])}")
        print(f"❌ Ошибок: {len(results['failed'])}")
        
        if results['downloaded']:
            print("\nСкачанные стандарты:")
            for name in results['downloaded']:
                print(f"  • {name}")
        
        if results['failed']:
            print("\nНе удалось скачать:")
            for name in results['failed']:
                print(f"  • {name}")
    
    if args.reload:
        print("\n📐 Перезагрузка стандартов в реестр...")
        results = load_all_standards(force_refresh=args.force)
        
        print(f"\n✅ Загружено: {len(results['loaded'])}")
        if results['loaded']:
            for item in results['loaded']:
                print(f"  • {item}")
        
        if results['warnings']:
            print(f"\n⚠️  Предупреждения: {len(results['warnings'])}")
            for warning in results['warnings'][:5]:  # Показываем первые 5
                print(f"  • {warning}")
        
        if results['errors']:
            print(f"\n❌ Ошибки: {len(results['errors'])}")
            for error in results['errors'][:5]:  # Показываем первые 5
                print(f"  • {error}")
    
    print("\n" + "=" * 60)


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(
        description="Управление базой стандартов CNC Assistant"
    )
    
    parser.add_argument(
        "command",
        choices=["update-standards", "reload", "download", "status"],
        help="Команда для выполнения"
    )
    
    parser.add_argument(
        "--download",
        action="store_true",
        help="Скачать стандарты из интернета"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Перезагрузить стандарты в реестр"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительно обновить данные"
    )
    
    args = parser.parse_args()
    
    if args.command == "update-standards":
        # Команда обновления (скачать + перезагрузить)
        args.download = True
        args.reload = True
        update_standards_command(args)
    
    elif args.command == "download":
        args.download = True
        update_standards_command(args)
    
    elif args.command == "reload":
        args.reload = True
        update_standards_command(args)
    
    elif args.command == "status":
        from standards.loader import get_standards_status
        
        print("=" * 60)
        print("  Статус базы стандартов")
        print("=" * 60)
        
        status = get_standards_status()
        
        print(f"\nРеестр доступен: {'✅' if status['registry_available'] else '❌'}")
        print(f"Эквивалентность доступна: {'✅' if status['equivalence_available'] else '❌'}")
        print(f"Данные ГОСТ доступны: {'✅' if status['gost_data_available'] else '❌'}")
        print(f"Данные ISO доступны: {'✅' if status['iso_data_available'] else '❌'}")
        
        downloader = StandardDownloader()
        downloaded = downloader.get_downloaded_standards()
        print(f"\nСкачано стандартов: {len(downloaded)}")
        
        print("=" * 60)


if __name__ == "__main__":
    main()
