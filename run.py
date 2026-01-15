"""
🏁 CNC Assistant - День 1: Чистый и простой запуск
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))


def check_environment():
    """Проверяет окружение и зависимости."""
    print("=" * 60)
    print("🤖 CNC Assistant - День 1")
    print("=" * 60)
    print("🚀 Версия: 1.0 - Минимальный рабочий прототип")
    print("🎯 Цель: Бот, который думает как человек")
    print("=" * 60)

    # 1. Проверяем файл окружения
    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_file.exists():
        print("\n📄 Файл .env не найден!")
        if env_example.exists():
            print("📋 Копирую .env.example в .env")
            try:
                import shutil
                shutil.copy(env_example, env_file)
                print("✅ Файл .env создан из примера")
                print("⚠️  Не забудьте вставить ваш реальный TELEGRAM_TOKEN в .env!")
            except Exception as e:
                print(f"❌ Ошибка копирования: {e}")
                return False
        else:
            # Создаем простой .env
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write("TELEGRAM_TOKEN=your_bot_token_here\n")
                f.write("LOG_LEVEL=INFO\n")
                f.write("DEFAULT_LANGUAGE=ru\n")
            print("✅ Создан простой .env файл")
            print("⚠️  Замените 'your_bot_token_here' на ваш реальный токен!")

    # 2. Загружаем переменные окружения
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("❌ python-dotenv не установлен!")
        print("📦 Установите: pip install python-dotenv")
        return False

    token = os.getenv('TELEGRAM_TOKEN')

    if not token or token == 'your_bot_token_here':
        print("\n❌ ТОКЕН НЕ НАСТРОЕН!")
        print("=" * 40)
        print("Шаги для получения токена:")
        print("1. Откройте Telegram")
        print("2. Найдите @BotFather")
        print("3. Создайте нового бота: /newbot")
        print("4. Скопируйте токен (выглядит как: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)")
        print("5. Вставьте токен в файл .env:")
        print("   TELEGRAM_TOKEN=ваш_токен_здесь")
        print("=" * 40)

        # Показываем содержимое .env файла если он есть
        if env_file.exists():
            print("\n📄 Содержимое .env файла:")
            with open(env_file, 'r') as f:
                print(f.read())
        return False

    # 3. Проверяем структуру данных
    data_dirs = ["data", "data/rules", "data/logs", "core", "bot"]

    for dir_path in data_dirs:
        dir_obj = Path(dir_path)
        if not dir_obj.exists():
            dir_obj.mkdir(parents=True, exist_ok=True)
            print(f"📁 Создана директория: {dir_path}")

    # 4. Проверяем необходимые файлы
    required_files = [
        Path("data/rules/cutting_modes.yaml"),
        Path("data/logs/dialogs.jsonl"),
        Path("core/__init__.py"),
        Path("bot/__init__.py")
    ]

    for file_path in required_files:
        if not file_path.exists():
            if file_path.name.endswith('.yaml'):
                # Создаем базовый YAML
                try:
                    import yaml
                    basic_rules = {
                        "materials": {
                            "steel": {
                                "name": "Сталь",
                                "cutting_speed": {"min": 80, "max": 150},
                                "feed": {"min": 0.1, "max": 0.3}
                            },
                            "aluminum": {
                                "name": "Алюминий",
                                "cutting_speed": {"min": 200, "max": 400},
                                "feed": {"min": 0.2, "max": 0.4}
                            },
                            "titanium": {
                                "name": "Титан",
                                "cutting_speed": {"min": 40, "max": 80},
                                "feed": {"min": 0.08, "max": 0.15}
                            }
                        },
                        "operations": {
                            "turning": {
                                "name": "Токарная обработка",
                                "default_tool": "токарный резец"
                            },
                            "milling": {
                                "name": "Фрезерование",
                                "default_tool": "концевая фреза"
                            }
                        }
                    }
                    with open(file_path, 'w', encoding='utf-8') as f:
                        yaml.dump(basic_rules, f, allow_unicode=True, default_flow_style=False)
                    print(f"📄 Создан файл: {file_path}")
                except ImportError:
                    print(f"❌ Не удалось создать {file_path}: yaml не установлен")
            elif file_path.name.endswith('.jsonl'):
                # Создаем пустой файл
                file_path.touch()
                print(f"📄 Создан файл: {file_path}")
            elif file_path.name == '__init__.py':
                # Создаем пустой __init__.py
                file_path.touch()
                print(f"📄 Создан файл: {file_path}")

    # 5. Проверяем зависимости
    print("\n🔍 Проверка зависимостей...")

    missing_packages = []

    # Проверяем каждую зависимость отдельно
    try:
        import telegram
    except ImportError:
        missing_packages.append('python-telegram-bot')

    try:
        import yaml
    except ImportError:
        missing_packages.append('pyyaml')

    try:
        from dotenv import load_dotenv
    except ImportError:
        missing_packages.append('python-dotenv')

    if missing_packages:
        print(f"❌ Не хватает зависимостей: {', '.join(missing_packages)}")
        print("\n📦 Установите недостающие пакеты:")
        print(f"pip install {' '.join(missing_packages)}")
        return False

    print("✅ Все зависимости установлены")

    print("\n✅ Окружение проверено и настроено!")
    print(f"🤖 Токен: {token[:10]}...")
    return True


def show_welcome():
    """Показывает приветственное сообщение."""
    welcome = """

    ╔══════════════════════════════════════════════════╗
    ║                                                  ║
    ║           CNC ASSISTANT - ДЕНЬ 1                 ║
    ║                                                  ║
    ║        Умный помощник для операторов ЧПУ         ║
    ║                                                  ║
    ╚══════════════════════════════════════════════════╝

    🎯 **Особенности этой версии:**

    1. 🧠 **Контекст** - помнит что вы говорили
    2. 🔄 **FSM** - логичные переходы между вопросами
    3. 🤖 **AI-мышление** - делает предположения
    4. 📚 **Память** - запоминает исправления
    5. 💬 **Естественный диалог** - как с человеком

    💡 **Примеры запросов:**
    • "токарка алюминия диаметр 50"
    • "фрезеровка стали 45"
    • "черновая обработка титана"
    • "посчитай режимы для стали"

    ⚠️  **Важно:** Бот учится на ваших исправлениях!
    Говорите "нет, подача 0.3 слишком большая" - он запомнит.

    """
    print(welcome)


def main():
    """Главная функция запуска."""
    try:
        # Проверяем окружение
        if not check_environment():
            print("\n❌ Не удалось настроить окружение")
            return 1

        show_welcome()

        print("\n🚀 Запускаю бота...")
        print("ℹ️  Для остановки нажмите Ctrl+C")
        print("=" * 60)

        # Импортируем и запускаем бота
        try:
            from bot.telegram_bot import main as run_bot
            run_bot()
        except ImportError as e:
            print(f"❌ Не удалось импортировать бота: {e}")
            print("📁 Проверьте структуру проекта:")
            print("• Есть ли папка bot/?")
            print("• Есть ли файл bot/telegram_bot.py?")
            return 1

    except KeyboardInterrupt:
        print("\n\n👋 Завершение работы...")
        return 0
    except Exception as e:
        print(f"\n❌ Ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())