"""
Простой Telegram бот для Дня 1.
"""

import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler as TGMessageHandler, Filters, CallbackContext

from core.handler import IntelligentHandler as CoreMessageHandler

# Минимальное логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

core_handler = CoreMessageHandler()


def start(update: Update, context: CallbackContext) -> None:
    """Начинаем новый диалог."""
    from core.context import reset_context
    user_id = update.effective_user.id
    reset_context(user_id)

    update.message.reply_text(
        "Привет! Я помогу с настройкой станка.\n\n"
        "Просто расскажи, что делаешь.\n"
        "Например: 'токарю алюминий' или 'фрезерую сталь 45'"
    )


def handle_text(update: Update, context: CallbackContext) -> None:
    """Обрабатывает все сообщения."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    print(f"Получено сообщение от {user_id}: '{text}'")

    try:
        response = core_handler.handle_message(user_id, text)
        update.message.reply_text(response, parse_mode='Markdown')

    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        update.message.reply_text("Что-то пошло не так. Попробуй /start")


def reset(update: Update, context: CallbackContext) -> None:
    """Сброс контекста."""
    from core.context import reset_context
    user_id = update.effective_user.id
    reset_context(user_id)
    update.message.reply_text(
        "🔄 Начинаем заново! Что обрабатываем?\n\n"
        "Например:\n• сталь 45 токарка\n• алюминий фрезеровка\n• титан черновая"
    )


def main() -> None:
    """Запуск бота."""
    # ⚠️ ЗАМЕНИТЕ ЭТОТ ТОКЕН НА ВАШ РЕАЛЬНЫЙ ТОКЕН ⚠️
    TOKEN = "8201932079:AAEUMoy2E22jUAUGZghGmOMPTDRrLAIfBh8"

    if not TOKEN or "ВАШ_ТОКЕН" in TOKEN:
        print("❌ ОШИБКА: Токен не установлен!")
        print("Замените TOKEN в коде на ваш реальный токен бота")
        return

    print(f"🤖 Запускаю бота... (токен: {TOKEN[:10]}...)")

    try:
        updater = Updater(TOKEN)
        dispatcher = updater.dispatcher

        # Команды
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("reset", reset))
        dispatcher.add_handler(TGMessageHandler(Filters.text & ~Filters.command, handle_text))

        updater.start_polling()
        print("✅ Бот запущен! Пишите /start в Telegram")
        print("=" * 50)
        updater.idle()

    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
        print("Проверьте токен и интернет-соединение")


if __name__ == '__main__':
    main()