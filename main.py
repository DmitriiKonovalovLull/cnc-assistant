"""
Главная точка входа в проект CNC Assistant.
Проверяет целостность проекта, зависимости и запускает выбранный режим работы.
"""

import sys
import os
import importlib
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Глобальный флаг загрузки стандартов
_standards_loaded = False


class ProjectChecker:
    """Класс для проверки целостности проекта."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.checked_files: List[Path] = []
        self.checked_dirs: List[Path] = []
    
    def check_file_exists(self, file_path: Path, required: bool = True) -> bool:
        """Проверить существование файла."""
        exists = file_path.exists() and file_path.is_file()
        if not exists:
            if required:
                self.errors.append(f"Отсутствует обязательный файл: {file_path}")
            else:
                self.warnings.append(f"Отсутствует опциональный файл: {file_path}")
        else:
            self.checked_files.append(file_path)
        return exists
    
    def check_dir_exists(self, dir_path: Path, required: bool = True) -> bool:
        """Проверить существование директории."""
        exists = dir_path.exists() and dir_path.is_dir()
        if not exists:
            if required:
                self.errors.append(f"Отсутствует обязательная директория: {dir_path}")
            else:
                self.warnings.append(f"Отсутствует опциональная директория: {dir_path}")
        else:
            self.checked_dirs.append(dir_path)
        return exists
    
    def check_import(self, module_name: str, required: bool = True) -> bool:
        """Проверить возможность импорта модуля."""
        try:
            importlib.import_module(module_name)
            return True
        except ImportError as e:
            if required:
                self.errors.append(f"Не удалось импортировать модуль {module_name}: {e}")
            else:
                self.warnings.append(f"Модуль {module_name} недоступен: {e}")
            return False
        except Exception as e:
            if required:
                self.errors.append(f"Ошибка при импорте {module_name}: {e}")
            else:
                self.warnings.append(f"Предупреждение при импорте {module_name}: {e}")
            return False
    
    def check_python_version(self) -> bool:
        """Проверить версию Python."""
        if sys.version_info < (3, 8):
            self.errors.append(f"Требуется Python 3.8+, текущая версия: {sys.version}")
            return False
        return True
    
    def check_project_structure(self) -> bool:
        """Проверить структуру проекта."""
        print("🔍 Проверка структуры проекта...")
        
        # Обязательные директории
        required_dirs = [
            PROJECT_ROOT / "app",
            PROJECT_ROOT / "app" / "bot",
            PROJECT_ROOT / "app" / "core",
            PROJECT_ROOT / "app" / "services",
            PROJECT_ROOT / "app" / "storage",
            PROJECT_ROOT / "standards",
        ]
        
        for dir_path in required_dirs:
            self.check_dir_exists(dir_path, required=True)
        
        # Обязательные файлы
        required_files = [
            PROJECT_ROOT / "requirements.txt",
            PROJECT_ROOT / "app" / "bot" / "telegram_bot.py",
            PROJECT_ROOT / "app" / "bot" / "handler.py",
        ]
        
        for file_path in required_files:
            self.check_file_exists(file_path, required=True)
        
        # Опциональные файлы
        optional_files = [
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / "app" / "storage" / "cnc.db",
        ]
        
        for file_path in optional_files:
            self.check_file_exists(file_path, required=False)
        
        return len(self.errors) == 0
    
    def check_dependencies(self) -> bool:
        """Проверить установленные зависимости."""
        print("📦 Проверка зависимостей...")
        
        # Критически важные зависимости
        critical_deps = [
            "aiogram",
            "sqlalchemy",
            "dotenv",
        ]
        
        for dep in critical_deps:
            module_name = dep.replace("-", "_")
            if dep == "dotenv":
                module_name = "dotenv"
            self.check_import(module_name, required=True)
        
        # Важные, но не критичные зависимости
        important_deps = [
            "yaml",
            "requests",
            "aiohttp",
        ]
        
        for dep in important_deps:
            self.check_import(dep, required=False)
        
        return len([e for e in self.errors if "импортировать модуль" in e]) == 0
    
    def check_env_file(self) -> bool:
        """Проверить наличие .env файла."""
        env_path = PROJECT_ROOT / ".env"
        if not env_path.exists():
            self.warnings.append(
                "Файл .env не найден. Telegram бот не сможет запуститься без TELEGRAM_TOKEN."
            )
            return False
        
        # Проверяем наличие TELEGRAM_TOKEN
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            token = os.getenv("TELEGRAM_TOKEN")
            if not token:
                self.warnings.append("TELEGRAM_TOKEN не найден в .env файле.")
                return False
            return True
        except Exception as e:
            self.warnings.append(f"Ошибка при чтении .env: {e}")
            return False
    
    def check_standards_module(self) -> bool:
        """Проверить модуль стандартов."""
        print("📐 Проверка модуля стандартов...")
        
        standards_modules = [
            "standards.registry.world_registry",
            "standards.equivalence.equivalence_engine",
            "standards.api.designation_handler",
            "standards.models",
            "standards.loader",
        ]
        
        for module in standards_modules:
            self.check_import(module, required=False)
        
        return True
    
    def run_all_checks(self) -> Tuple[bool, List[str], List[str]]:
        """Запустить все проверки."""
        print("\n" + "=" * 60)
        print("  CNC Assistant - Проверка целостности проекта")
        print("=" * 60 + "\n")
        
        # Проверка версии Python
        if not self.check_python_version():
            return False, self.errors, self.warnings
        
        # Проверка структуры проекта
        structure_ok = self.check_project_structure()
        
        # Проверка зависимостей
        deps_ok = self.check_dependencies()
        
        # Проверка .env файла
        env_ok = self.check_env_file()
        
        # Проверка модуля стандартов
        standards_ok = self.check_standards_module()
        
        # Итоговый результат
        all_ok = structure_ok and deps_ok
        
        return all_ok, self.errors, self.warnings


def print_check_results(errors: List[str], warnings: List[str]) -> None:
    """Вывести результаты проверки."""
    print("\n" + "=" * 60)
    print("  Результаты проверки")
    print("=" * 60)
    
    if errors:
        print("\n❌ ОШИБКИ:")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
    
    if warnings:
        print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
    
    if not errors and not warnings:
        print("\n✅ Все проверки пройдены успешно!")
    elif not errors:
        print("\n✅ Критических ошибок не обнаружено.")
    else:
        print("\n❌ Обнаружены критические ошибки. Исправьте их перед запуском.")
    
    print("=" * 60 + "\n")


def show_main_menu() -> str:
    """Показать главное меню и получить выбор пользователя."""
    print("\n" + "=" * 60)
    print("  CNC Assistant - Главное меню")
    print("=" * 60)
    print("\nВыберите действие:")
    print("  1. Запустить Telegram бот (основной режим)")
    print("  2. Проверка целостности проекта")
    print("  3. Установка зависимостей")
    print("  4. Обновить базу стандартов")
    print("  5. Запустить тесты")
    print("  0. Выход")
    print()
    
    choice = input("Ваш выбор (0-5): ").strip()
    return choice


def run_telegram_bot() -> None:
    """Запустить Telegram бота."""
    print("\n🚀 Запуск Telegram бота...")
    
    bot_path = PROJECT_ROOT / "app" / "bot" / "telegram_bot.py"
    if not bot_path.exists():
        print(f"❌ Файл бота не найден: {bot_path}")
        return
    
    try:
        # Проверяем наличие токена
        from dotenv import load_dotenv
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            print("❌ Файл .env не найден. Создайте его с TELEGRAM_TOKEN.")
            return
        
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            print("❌ TELEGRAM_TOKEN не найден в .env файле.")
            return
        
        # Убеждаемся, что стандарты загружены перед запуском бота
        if not _standards_loaded:
            print("📐 Загрузка стандартов перед запуском бота...")
            load_standards_on_startup()
        
        # Запускаем бота
        print("✅ Токен найден. Запуск бота...")
        print("   (Стандарты будут автоматически загружены при инициализации)")
        import subprocess
        subprocess.run([sys.executable, str(bot_path)], check=True)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Бот остановлен пользователем.")
    except Exception as e:
        print(f"\n❌ Ошибка при запуске бота: {e}")
        logger.exception("Ошибка при запуске Telegram бота")




def update_standards() -> None:
    """Обновить базу стандартов."""
    print("\n📐 Обновление базы стандартов...")
    
    try:
        from standards.cli.update_standards import update_standards_command
        import argparse
        
        # Создаем аргументы для команды обновления
        args = argparse.Namespace(
            download=True,
            reload=True,
            force=False
        )
        
        update_standards_command(args)
        
    except ImportError as e:
        print(f"❌ Не удалось импортировать модуль обновления стандартов: {e}")
    except Exception as e:
        print(f"❌ Ошибка при обновлении стандартов: {e}")
        logger.exception("Ошибка обновления стандартов")


def run_tests() -> None:
    """Запустить тесты стандартов."""
    print("\n🧪 Запуск тестов стандартов...")
    
    try:
        import subprocess
        import sys
        
        # Запускаем pytest для тестов стандартов
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/standards", "-v"],
            cwd=str(PROJECT_ROOT),
            capture_output=False
        )
        
        if result.returncode == 0:
            print("\n✅ Все тесты пройдены успешно!")
        else:
            print(f"\n❌ Некоторые тесты не прошли (код выхода: {result.returncode})")
    
    except ImportError:
        print("❌ pytest не установлен. Установите: pip install pytest")
    except Exception as e:
        print(f"❌ Ошибка при запуске тестов: {e}")
        logger.exception("Ошибка запуска тестов")


def install_dependencies() -> None:
    """Установить зависимости из requirements.txt."""
    print("\n📦 Установка зависимостей...")
    
    requirements_path = PROJECT_ROOT / "requirements.txt"
    if not requirements_path.exists():
        print(f"❌ Файл requirements.txt не найден: {requirements_path}")
        return
    
    try:
        print(f"Выполняется: pip install -r {requirements_path}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)],
            check=False
        )
        
        if result.returncode == 0:
            print("✅ Зависимости успешно установлены!")
        else:
            print("❌ Ошибка при установке зависимостей.")
            print("   Попробуйте выполнить вручную: pip install -r requirements.txt")
    
    except Exception as e:
        print(f"❌ Ошибка при установке зависимостей: {e}")


def load_standards_on_startup() -> None:
    """Загрузить стандарты при старте приложения."""
    global _standards_loaded
    
    if _standards_loaded:
        return
    
    try:
        print("\n📐 Автозагрузка стандартов...")
        from standards.loader import load_all_standards
        
        results = load_all_standards(force_refresh=False)
        
        if results["loaded"]:
            print("✅ Загружено:")
            for item in results["loaded"]:
                print(f"   • {item}")
        
        if results["warnings"]:
            print("⚠️  Предупреждения:")
            for warning in results["warnings"]:
                print(f"   • {warning}")
        
        if results["errors"]:
            print("❌ Ошибки:")
            for error in results["errors"]:
                print(f"   • {error}")
        
        _standards_loaded = True
        
    except ImportError as e:
        print(f"⚠️  Модуль стандартов недоступен: {e}")
    except Exception as e:
        print(f"⚠️  Ошибка при загрузке стандартов: {e}")
        logger.exception("Ошибка автозагрузки стандартов")


def main():
    """Главная функция."""
    global _standards_loaded
    
    try:
        # Сначала проверяем проект
        checker = ProjectChecker()
        all_ok, errors, warnings = checker.run_all_checks()
        
        print_check_results(errors, warnings)
        
        # Автозагрузка стандартов
        load_standards_on_startup()
        
        # Если есть критические ошибки, предлагаем их исправить
        if errors:
            print("\n⚠️  Обнаружены критические ошибки.")
            choice = input("Продолжить несмотря на ошибки? (y/n): ").strip().lower()
            if choice != 'y':
                print("Завершение работы.")
                return
        
        # Проверяем наличие .env и токена для бота
        from dotenv import load_dotenv
        env_path = PROJECT_ROOT / ".env"
        has_env = env_path.exists()
        
        if has_env:
            load_dotenv(env_path)
            token = os.getenv("TELEGRAM_TOKEN")
            if token and token != "YOUR_BOT_TOKEN":
                # Если есть токен, сразу запускаем бота
                print("\n✅ Токен найден. Запуск Telegram бота...")
                run_telegram_bot()
                return
        
        # Если нет токена, показываем меню для настройки
        print("\n💡 Для запуска бота нужен TELEGRAM_TOKEN в файле .env")
        print("   Используйте меню для настройки проекта\n")
        
        # Главное меню (только для настройки)
        while True:
            choice = show_main_menu()
            
            if choice == "0":
                print("\nДо свидания!")
                break
            
            elif choice == "1":
                run_telegram_bot()
                # После остановки бота не возвращаемся в меню
                break
            
            elif choice == "2":
                # Повторная проверка
                checker = ProjectChecker()
                all_ok, errors, warnings = checker.run_all_checks()
                print_check_results(errors, warnings)
                input("\nНажмите Enter для продолжения...")
            
            elif choice == "3":
                install_dependencies()
                input("\nНажмите Enter для продолжения...")
            
            elif choice == "4":
                update_standards()
                input("\nНажмите Enter для продолжения...")
            
            elif choice == "5":
                run_tests()
                input("\nНажмите Enter для продолжения...")
            
            else:
                print("❌ Неверный выбор. Попробуйте снова.")
                input("\nНажмите Enter для продолжения...")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем. До свидания!")
    except Exception as e:
        logger.exception("Критическая ошибка в main.py")
        print(f"\n❌ Критическая ошибка: {e}")
        print("   Проверьте логи для подробностей.")


if __name__ == "__main__":
    main()
