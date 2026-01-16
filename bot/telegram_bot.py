"""
🏁 CNC Assistant - Главный файл запуска (упрощенная версия)
"""

import os
import sys
from pathlib import Path

# Определяем корневую директорию проекта
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Создаем необходимые директории
LOG_DIR = ROOT_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

CONTEXT_DIR = ROOT_DIR / "data" / "contexts"
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

RULES_DIR = ROOT_DIR / "data" / "rules"
RULES_DIR.mkdir(parents=True, exist_ok=True)

# Получаем токен из переменных окружения
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TOKEN or TOKEN == 'your_bot_token_here':
    print("\n" + "=" * 60)
    print("❌ ТОКЕН НЕ НАСТРОЕН!")
    print("=" * 60)
    print("📋 Чтобы получить токен:")
    print("1. Откройте Telegram")
    print("2. Найдите @BotFather")
    print("3. Создайте бота: /newbot")
    print("4. Скопируйте токен")
    print("5. Вставьте в файл .env:")
    print("   TELEGRAM_TOKEN=ваш_токен_здесь")
    print("=" * 60)

    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        env_file.parent.mkdir(parents=True, exist_ok=True)
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("TELEGRAM_TOKEN=your_bot_token_here\n")
        print(f"✅ Создан файл .env: {env_file}")

    exit(1)

print(f"🤖 Запуск CNC Assistant с токеном: {TOKEN[:10]}...")
print(f"📁 Корневая директория: {ROOT_DIR}")


# ==================== ФУНКЦИИ ОБРАБОТКИ СООБЩЕНИЙ ====================

def handle_start() -> str:
    """Обработка команды /start."""
    return (
        "👋 Привет! Я CNC Assistant - бот для расчета режимов резания.\n\n"
        "🎯 **Что я умею:**\n"
        "• Рассчитывать скорости, подачи, глубины резания\n"
        "• Работать с разными материалами и операциями\n\n"
        "💡 **Пример запроса:**\n"
        "`токарка алюминия диаметр 50 мм`\n"
        "`фрезеровка стали 45 чистовая`\n"
        "`титан с 200 до 150`\n\n"
        "Напишите ваш запрос в одном сообщении!"
    )


def handle_help() -> str:
    """Обработка команды /help."""
    return (
        "🆘 **Справка по формату запросов**\n\n"
        "📋 **Обязательно укажите:**\n"
        "1. Материал (алюминий, сталь, титан, нержавейка)\n"
        "2. Операция (токарка, фрезеровка, расточка)\n"
        "3. Размер (диаметр 50 или с 100 до 95)\n\n"
        "💡 **Примеры:**\n"
        "• токарка алюминия диаметр 50\n"
        "• титан с 200 до 150\n"
        "• фрезеровка стали 45 чистовая\n"
        "• расточка нержавейки Ø80 черновая\n\n"
        "⚠️ **Важно:** Всё в одном сообщении!"
    )


def handle_reset() -> str:
    """Обработка команды /reset."""
    return "🔄 Контекст сброшен. Начните новый запрос."


def calculate_cutting_parameters(text: str) -> str:
    """Рассчитывает параметры резания."""
    text_lower = text.lower()

    # Определяем материал
    if 'алюмин' in text_lower:
        material = "алюминий"
        speed = "200-400 м/мин"
        feed = "0.2-0.4 мм/об"
        depth = "1.5-4.0 мм"
    elif 'стал' in text_lower:
        material = "сталь"
        speed = "80-150 м/мин"
        feed = "0.1-0.3 мм/об"
        depth = "1.0-3.0 мм"
    elif 'титан' in text_lower:
        material = "титан"
        speed = "40-80 м/мин"
        feed = "0.08-0.15 мм/об"
        depth = "0.5-1.5 мм"
    elif 'нержавей' in text_lower:
        material = "нержавейка"
        speed = "60-100 м/мин"
        feed = "0.1-0.25 мм/об"
        depth = "1.0-2.5 мм"
    else:
        material = "неизвестный"
        speed = "100-200 м/мин"
        feed = "0.1-0.3 мм/об"
        depth = "1.0-3.0 мм"

    # Определяем операцию
    if 'токар' in text_lower:
        operation = "токарная"
        tool = "токарный резец"
    elif 'фрезер' in text_lower:
        operation = "фрезерная"
        tool = "концевая фреза"
    elif 'расточ' in text_lower:
        operation = "расточная"
        tool = "расточной резец"
    elif 'сверл' in text_lower:
        operation = "сверление"
        tool = "спиральное сверло"
    else:
        operation = "неизвестная"
        tool = "стандартный инструмент"

    # Определяем режим
    if 'чистов' in text_lower:
        mode = "чистовая"
        feed = "0.1-0.2 мм/об"
    elif 'чернов' in text_lower:
        mode = "черновая"
        feed = "0.2-0.4 мм/об"
    else:
        mode = "стандартный"

    return (
        f"⚙️ **Режимы резания для {material}:**\n\n"
        f"**Операция:** {operation}\n"
        f"**Инструмент:** {tool}\n"
        f"**Режим:** {mode}\n\n"
        f"📊 **Рекомендуемые параметры:**\n"
        f"• Скорость резания: {speed}\n"
        f"• Подача: {feed}\n"
        f"• Глубина резания: {depth}\n\n"
        f"💡 **Для точного расчета укажите:**\n"
        f"• Точный материал (например: сталь 45)\n"
        f"• Диаметр заготовки\n"
        f"• Целевую чистоту поверхности\n"
        f"• Тип инструмента\n\n"
        f"🔄 **Попробуйте уточнить запрос!**"
    )


def handle_text_message(text: str) -> str:
    """Обрабатывает текстовое сообщение."""
    text_lower = text.lower().strip()

    # Команды
    if text_lower == '/start':
        return handle_start()
    elif text_lower == '/help':
        return handle_help()
    elif text_lower == '/reset':
        return handle_reset()
    elif text_lower.startswith('/'):
        return f"❌ Неизвестная команда: {text_lower}\n\nИспользуйте /start для начала работы."

    # Проверяем, похож ли запрос на расчет параметров
    materials = ['алюмин', 'стал', 'титан', 'нержавей']
    operations = ['токар', 'фрезер', 'расточ', 'сверл']

    if any(word in text_lower for word in materials):
        if any(word in text_lower for word in operations):
            return calculate_cutting_parameters(text_lower)

    # Неправильный формат
    display_text = text[:50] + "..." if len(text) > 50 else text
    return (
        f"📝 **Ваш запрос:** `{display_text}`\n\n"
        "🤔 Не могу разобрать запрос.\n\n"
        "💡 **Правильный формат:**\n"
        "`<материал> <операция> <размер> [режим]`\n\n"
        "**Пример:**\n"
        "• токарка алюминия диаметр 50\n"
        "• фрезеровка стали 45 чистовая\n"
        "• титан с 200 до 150\n\n"
        "Попробуйте еще раз!"
    )


# ==================== TELEGRAM БОТ ====================

def create_telegram_bot():
    """Создает и настраивает Telegram бота."""
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
        print("✅ python-telegram-bot импортирован")
    except ImportError:
        print("\n" + "=" * 60)
        print("❌ БИБЛИОТЕКА НЕ УСТАНОВЛЕНА")
        print("=" * 60)
        print("Установите python-telegram-bot версии 20.0+:")
        print("pip install python-telegram-bot")
        print("=" * 60)
        return None

    # Функции-обработчики
    async def start_command(update: Update, context):
        await update.message.reply_text(handle_start())

    async def help_command(update: Update, context):
        await update.message.reply_text(handle_help())

    async def reset_command(update: Update, context):
        await update.message.reply_text(handle_reset())

    async def text_message_handler(update: Update, context):
        text = update.message.text
        response = handle_text_message(text)
        await update.message.reply_text(response)

    async def error_handler(update: Update, context):
        print(f"❌ Ошибка: {context.error}")

    try:
        print("🤖 Создаю Telegram приложение...")
        application = Application.builder().token(TOKEN).build()

        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("reset", reset_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
        application.add_error_handler(error_handler)

        print("✅ Приложение создано")
        return application

    except Exception as e:
        print(f"❌ Ошибка создания приложения: {e}")
        return None


# ==================== CLI РЕЖИМ ====================

def run_cli_mode():
    """Запускает CLI режим."""
    print("\n" + "=" * 60)
    print("🧪 Тестовый режим CNC Assistant")
    print("=" * 60)
    print("💡 **Доступные команды:**")
    print("• /start - начало работы")
    print("• /help - справка")
    print("• /reset - сброс")
    print("• /exit - выход")
    print("• <запрос> - расчет параметров")
    print("=" * 60)

    while True:
        try:
            text = input("\n📝 Ваш запрос: ").strip()

            if text.lower() in ['/exit', 'exit', 'выход', 'quit']:
                print("👋 Завершение работы...")
                break

            if not text:
                continue

            response = handle_text_message(text)
            print("\n" + "=" * 60)
            print("🤖 Ответ:")
            print(response)
            print("=" * 60)

        except KeyboardInterrupt:
            print("\n👋 Завершение работы...")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")


# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

def main():
    """Главная функция запуска."""
    print("\n" + "=" * 60)
    print("🚀 Запуск CNC Assistant")
    print("=" * 60)

    # Проверяем структуру проекта
    print(f"\n📁 Структура проекта:")
    print(f"• Корень: {ROOT_DIR}")
    print(f"• Логи: {LOG_DIR} {'✅' if LOG_DIR.exists() else '❌'}")
    print(f"• Правила: {RULES_DIR} {'✅' if RULES_DIR.exists() else '❌'}")

    # Создаем файл правил если его нет
    yaml_file = RULES_DIR / "cutting_modes.yaml"
    if not yaml_file.exists():
        yaml_file.parent.mkdir(parents=True, exist_ok=True)
        default_rules = """materials:
  сталь:
    speed_min: 80
    speed_max: 150
    feed_min: 0.1
    feed_max: 0.3
    depth_min: 1.0
    depth_max: 3.0

  алюминий:
    speed_min: 200
    speed_max: 400
    feed_min: 0.2
    feed_max: 0.4
    depth_min: 1.5
    depth_max: 4.0

  титан:
    speed_min: 40
    speed_max: 80
    feed_min: 0.08
    feed_max: 0.15
    depth_min: 0.5
    depth_max: 1.5
"""
        with open(yaml_file, 'w', encoding='utf-8') as f:
            f.write(default_rules)
        print(f"✅ Создан файл правил: {yaml_file}")

    # Создаем Telegram бота
    print("\n🤖 Создаю Telegram бота...")
    application = create_telegram_bot()

    if application:
        print("\n" + "=" * 60)
        print("✅ CNC Assistant ЗАПУЩЕН!")
        print("=" * 60)
        print("📱 Откройте Telegram и найдите вашего бота")
        print("💬 Напишите /start чтобы начать")
        print("\n⚡ **Доступные команды:**")
        print("• /start - начало работы")
        print("• /help - справка по формату")
        print("• /reset - сброс контекста")
        print("\n💡 **Примеры запросов:**")
        print("• токарка алюминия диаметр 50")
        print("• титан с 200 до 150")
        print("• фрезеровка стали 45 чистовая")
        print("=" * 60)

        try:
            # Запускаем бота
            print("\n🔄 Запускаю бота...")
            application.run_polling(drop_pending_updates=True)
        except KeyboardInterrupt:
            print("\n👋 Бот остановлен")
        except Exception as e:
            print(f"\n❌ Ошибка при работе бота: {e}")
            print("\n🔄 Переключаюсь в CLI режим...")
            run_cli_mode()
    else:
        print("\n❌ Не удалось создать Telegram бота")
        print("🔄 Переключаюсь в CLI режим...")
        run_cli_mode()


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Завершение работы...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()
        run_cli_mode()
