"""
🏁 CNC Assistant - Главный файл запуска (исправленная версия)
"""

import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Any

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('data/logs/bot_main.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Получаем токен
TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TOKEN or TOKEN == 'your_bot_token_here':
    logger.error("❌ TELEGRAM_TOKEN не найден в .env файле!")
    print("\n" + "=" * 60)
    print("❌ ТОКЕН НЕ НАСТРОЕН!")
    print("=" * 60)
    print("📋 Чтобы получить токен:")
    print("1. Откройте Telegram")
    print("2. Найдите @BotFather")
    print("3. Создайте бота: /newbot")
    print("4. Скопируйте токен (пример: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)")
    print("5. Вставьте в файл .env:")
    print("   TELEGRAM_TOKEN=ваш_токен_здесь")
    print("=" * 60)
    exit(1)

print(f"🤖 Запуск CNC Assistant с токеном: {TOKEN[:10]}...")
print("⚙️  Проверка архитектуры...")


# ==================== ИСПРАВЛЕННЫЙ FALLBACK ====================

class StatelessFallback:
    """Stateless Fallback Handler - UX-помощник без состояния."""

    def __init__(self):
        logger.info("🔄 Stateless Fallback инициализирован")

    @staticmethod
    def _handle_start() -> str:
        """Приветствие без состояния."""
        return (
            "👋 Привет! Я CNC Assistant.\n\n"
            "💡 **Опишите задачу в одном сообщении:**\n"
            "• `токарка алюминия диаметр 50`\n"
            "• `титан с 200 до 150 чистота 0.8`\n"
            "• `фрезеровка стали 45 чистовая`\n\n"
            "📋 **Что нужно указать:**\n"
            "1. Материал (алюминий, сталь, титан)\n"
            "2. Операция (токарка, фрезеровка)\n"
            "3. Диаметр (или цель: с X до Y)\n"
            "4. [опционально] Черновая/чистовая\n\n"
            "Попробуйте отправить полный запрос!"
        )

    @staticmethod
    def _handle_help() -> str:
        """Справка без рекомендаций."""
        return (
            "🆘 **Справка по формату запросов:**\n\n"
            "💡 **Полный пример запроса:**\n"
            "```\n"
            "титан токарка с 200 до 150 чистота 0.8\n"
            "```\n\n"
            "📋 **Обязательные данные:**\n"
            "✅ Материал (алюминий, сталь, титан, нержавейка)\n"
            "✅ Операция (токарка, фрезеровка, расточка, сверление)\n"
            "✅ Диаметр (50) или цель (с 200 до 150)\n\n"
            "📊 **Дополнительно можно указать:**\n"
            "• черновая / чистовая\n"
            "• чистота Ra (например: Ra 0.8)\n"
            "• допуск (±0.1)\n\n"
            "⚠️  **Важно:** Укажите всё в одном сообщении."
        )

    @staticmethod
    def _handle_reset() -> str:
        """Сброс (только сообщение)."""
        return (
            "🔄 Команда /reset в fallback режиме\n\n"
            "В этом режиме я НЕ храню контекст.\n"
            "Просто отправьте новый запрос в правильном формате.\n\n"
            "💡 **Примеры новых запросов:**\n"
            "• `алюминий фрезеровка диаметр 20`\n"
            "• `сталь токарка с 100 до 95`\n"
            "• `титан чистовая Ra 1.6`"
        )

    @staticmethod
    def _unknown_command(command: str) -> str:
        """Неизвестная команда."""
        return (
            f"❌ Неизвестная команда: {command}\n\n"
            "📋 **Доступные команды:**\n"
            "/start - начало работы\n"
            "/help - справка по формату\n"
            "/reset - информация о сбросе\n\n"
            "💡 **Или просто опишите задачу:**\n"
            "`токарка алюминия диаметр 50`"
        )

    @staticmethod
    def _show_format_examples(original_text: str) -> str:
        """Показывает примеры формата БЕЗ анализа текста."""
        display_text = original_text[:50] + ("..." if len(original_text) > 50 else "")

        return (
            f"📝 **Запрос:** `{display_text}`\n\n"
            "🤔 **Правильный формат запросов:**\n"
            "```\n"
            "титан токарка с 200 до 150 чистота 0.8\n"
            "алюминий фрезеровка диаметр 20\n"
            "сталь 45 расточка черновая\n"
            "```\n\n"
            "📋 **Что указать:**\n"
            "1. **Материал:** алюминий/сталь/титан\n"
            "2. **Операция:** токарка/фрезеровка\n"
            "3. **Размер:** диаметр ИЛИ цель\n"
            "4. **[опционально]** режим/чистота\n\n"
            "🔄 **Попробуйте в таком формате!**"
        )

    def handle_message(self, text: str) -> str:
        """Обрабатывает сообщение БЕЗ хранения состояния."""
        text_lower = text.lower().strip()

        # Команды
        if text_lower == '/start':
            return self._handle_start()
        elif text_lower == '/help':
            return self._handle_help()
        elif text_lower == '/reset':
            return self._handle_reset()
        elif text_lower.startswith('/'):
            return self._unknown_command(text_lower)

        # Любой другой текст - показываем формат
        return self._show_format_examples(text)


# ==================== ГЛАВНЫЙ ОБРАБОТЧИК ====================

class MainHandler:
    """Главный обработчик с интеллектуальным fallback."""

    def __init__(self):
        self.fallback = StatelessFallback()
        self.use_fallback_only = False
        self.main_system_loaded = False
        self._main_handle_func = None
        self._try_load_main_system()

    def _try_load_main_system(self):
        """Пытается загрузить основную систему."""
        try:
            # Пробуем импортировать основные модули
            from bot.handlers.message_handler import handle_message as main_handle

            self._main_handle_func = main_handle
            self.main_system_loaded = True
            logger.info("✅ Основная система загружена")

        except ImportError as import_err:
            logger.warning(f"⚠️  Основная система недоступна: {import_err}")
            self.main_system_loaded = False
            self.use_fallback_only = True

        except Exception as err:
            logger.error(f"❌ Ошибка загрузки основной системы: {err}")
            self.main_system_loaded = False
            self.use_fallback_only = True

    def handle_message(self, user_id: str, text: str) -> str:
        """Умная обработка с автоматическим fallback."""
        text = text.strip()

        if not text:
            return "Пожалуйста, введите текст."

        # Если включен режим только fallback
        if self.use_fallback_only:
            return self.fallback.handle_message(text)

        # Пытаемся использовать основную систему
        try:
            if self.main_system_loaded and self._main_handle_func:
                # Передаем в основную систему
                return self._main_handle_func(user_id, text)
            else:
                # Используем fallback
                return self.fallback.handle_message(text)

        except (ImportError, RuntimeError) as critical_err:
            # Критические ошибки - переключаемся на fallback
            logger.error(f"❌ Критическая ошибка, переключаюсь на fallback: {critical_err}")
            self.use_fallback_only = True
            return self.fallback.handle_message(text)

        except Exception as other_err:
            # Другие ошибки - пробуем fallback, но логируем
            logger.error(f"⚠️  Ошибка в основной системе: {other_err}")
            try:
                if self._main_handle_func:
                    return self._main_handle_func(user_id, text)
            except Exception as nested_err:
                logger.error(f"⚠️  Повторная ошибка: {nested_err}")

            return self.fallback.handle_message(text)

    def handle_command(self, user_id: str, command: str) -> str:
        """Обрабатывает команды."""
        command_lower = command.lower().strip()

        if command_lower == '/fallback':
            self.use_fallback_only = True
            return "✅ Переключился на fallback режим"

        elif command_lower == '/main':
            if self.main_system_loaded:
                self.use_fallback_only = False
                return "✅ Переключился на основную систему"
            else:
                return "❌ Основная система недоступна"

        elif command_lower == '/status':
            status = "✅ Основная система" if not self.use_fallback_only else "🔄 Fallback режим"
            loaded = "✅ Загружена" if self.main_system_loaded else "❌ Не загружена"
            return f"📊 **Статус системы:**\n• Режим: {status}\n• Основная система: {loaded}"

        else:
            # Пробуем обработать как обычное сообщение
            return self.handle_message(user_id, command)


# ==================== TELEGRAM ИНТЕГРАЦИЯ ====================

def setup_telegram_bot() -> Optional[Any]:
    """Настраивает и запускает Telegram бота."""
    telegram_available = False

    try:
        from telegram import Update
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
        telegram_available = True

    except ImportError as import_err:
        logger.error(f"❌ python-telegram-bot не установлен: {import_err}")
        print("\n📦 Установите зависимости:")
        print("pip install python-telegram-bot python-dotenv pyyaml")
        return None

    if not telegram_available:
        return None

    # Создаем главный обработчик
    main_handler = MainHandler()

    # Обработчики для Telegram
    async def start_command(update: Update, context: CallbackContext) -> None:
        """Обрабатывает /start."""
        user_id = str(update.effective_user.id)
        response = main_handler.handle_message(user_id, "/start")
        await update.message.reply_text(response, parse_mode='Markdown')

    async def help_command(update: Update, context: CallbackContext) -> None:
        """Обрабатывает /help."""
        user_id = str(update.effective_user.id)
        response = main_handler.handle_message(user_id, "/help")
        await update.message.reply_text(response, parse_mode='Markdown')

    async def reset_command(update: Update, context: CallbackContext) -> None:
        """Обрабатывает /reset."""
        user_id = str(update.effective_user.id)
        response = main_handler.handle_message(user_id, "/reset")
        await update.message.reply_text(response, parse_mode='Markdown')

    async def fallback_command(update: Update, context: CallbackContext) -> None:
        """Обрабатывает /fallback."""
        user_id = str(update.effective_user.id)
        response = main_handler.handle_command(user_id, "/fallback")
        await update.message.reply_text(response, parse_mode='Markdown')

    async def main_command(update: Update, context: CallbackContext) -> None:
        """Обрабатывает /main."""
        user_id = str(update.effective_user.id)
        response = main_handler.handle_command(user_id, "/main")
        await update.message.reply_text(response, parse_mode='Markdown')

    async def status_command(update: Update, context: CallbackContext) -> None:
        """Обрабатывает /status."""
        user_id = str(update.effective_user.id)
        response = main_handler.handle_command(user_id, "/status")
        await update.message.reply_text(response, parse_mode='Markdown')

    async def handle_text_message(update: Update, context: CallbackContext) -> None:
        """Обрабатывает текстовые сообщения."""
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()

        logger.info(f"📨 Сообщение от {user_id}: {text}")

        try:
            response = main_handler.handle_message(user_id, text)
            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as err:
            logger.error(f"❌ Ошибка обработки: {err}")
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                parse_mode='Markdown'
            )

    def setup_dispatcher(dispatcher):
        """Настраивает диспетчер команд."""
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("reset", reset_command))
        dispatcher.add_handler(CommandHandler("fallback", fallback_command))
        dispatcher.add_handler(CommandHandler("main", main_command))
        dispatcher.add_handler(CommandHandler("status", status_command))
        dispatcher.add_handler(MessageHandler(Filters.TEXT & ~Filters.COMMAND, handle_text_message))

        logger.info("✅ Диспетчер команд настроен")

    # Функция для запуска бота
    def start_bot():
        """Запускает Telegram бота."""
        try:
            # Создаем Updater с правильной версией библиотеки
            updater = Updater(TOKEN)
            dispatcher = updater.dispatcher

            # Настраиваем диспетчер
            setup_dispatcher(dispatcher)

            # Запускаем бота
            updater.start_polling()
            logger.info("✅ Бот запущен и готов к работе!")

            return updater

        except Exception as bot_err:
            logger.error(f"❌ Ошибка запуска бота: {bot_err}")
            return None

    return start_bot


# ==================== CLI ТЕСТОВЫЙ РЕЖИМ ====================

def run_cli_test_mode():
    """Запускает тестовый режим в командной строке."""
    print("\n" + "=" * 60)
    print("🧪 Тестовый режим CNC Assistant")
    print("=" * 60)

    main_handler = MainHandler()

    print("📊 Статус системы:")
    if main_handler.main_system_loaded:
        print("✅ Основная система загружена")
    else:
        print("🔄 Используется fallback режим")

    print("\n💡 Примеры запросов:")
    print("• /start - начало работы")
    print("• токарка алюминия диаметр 50")
    print("• титан с 200 до 150 чистота 0.8")
    print("• /status - статус системы")
    print("• /exit - выход")
    print("=" * 60)

    user_id = "cli_user_001"

    while True:
        try:
            text = input("\n📝 Ваш запрос: ").strip()

            if text.lower() in ['/exit', 'exit', 'quit', 'выход']:
                print("\n👋 Завершение работы...")
                break

            if not text:
                print("⚠️  Пожалуйста, введите текст")
                continue

            print("\n🤖 Ответ бота:")
            print("-" * 50)
            response = main_handler.handle_message(user_id, text)
            print(response)
            print("-" * 50)

        except KeyboardInterrupt:
            print("\n\n👋 Завершение работы...")
            break
        except Exception as err:
            print(f"\n❌ Ошибка: {err}")


# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

def main():
    """Главная функция запуска."""
    print("\n" + "=" * 60)
    print("🚀 Запуск CNC Assistant")
    print("=" * 60)

    # Проверяем базовые зависимости
    try:
        # Проверяем наличие python-dotenv
        from dotenv import load_dotenv
        load_dotenv()

        # Проверяем наличие pyyaml
        try:
            import yaml
        except ImportError:
            print("⚠️  pyyaml не установлен. Установите: pip install pyyaml")
            print("Бот будет работать, но некоторые функции могут быть недоступны.")

        print("✅ Базовые зависимости проверены")

    except ImportError as import_err:
        print(f"⚠️  Ошибка импорта: {import_err}")
        print("📦 Установите зависимости:")
        print("pip install python-dotenv pyyaml")
        print("\n🔄 Запускаю CLI тестовый режим...")
        run_cli_test_mode()
        return

    # Пытаемся запустить Telegram бота
    start_bot_func = setup_telegram_bot()

    if start_bot_func:
        try:
            # Запускаем Telegram бота
            print("🤖 Запускаю Telegram бота...")
            updater = start_bot_func()

            if updater:
                print("✅ Бот запущен и готов к работе!")
                print("📱 Откройте Telegram и найдите вашего бота")
                print("💬 Напишите /start чтобы начать")
                print("\n⚡ Доступные команды:")
                print("• /start - начало работы")
                print("• /help - справка")
                print("• /reset - сброс контекста")
                print("• /status - статус системы")
                print("• /fallback - переключиться на fallback")
                print("• /main - переключиться на основную систему")
                print("\n🔄 Для остановки нажмите Ctrl+C")
                print("=" * 60)

                # Держим бота запущенным
                updater.idle()

            else:
                print("❌ Не удалось запустить Telegram бота")
                print("🔄 Запускаю CLI тестовый режим...")
                run_cli_test_mode()

        except KeyboardInterrupt:
            print("\n\n👋 Бот остановлен пользователем")
        except Exception as bot_err:
            print(f"\n❌ Ошибка Telegram бота: {bot_err}")
            print("🔄 Запускаю CLI тестовый режим...")
            run_cli_test_mode()
    else:
        print("🔄 Telegram недоступен, запускаю CLI тестовый режим...")
        run_cli_test_mode()


# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 CNC Assistant завершил работу")
        sys.exit(0)
    except Exception as critical_err:
        logger.error(f"❌ Критическая ошибка: {critical_err}")
        print(f"\n❌ Критическая ошибка: {critical_err}")
        print("🔄 Запускаю CLI тестовый режим...")
        run_cli_test_mode()