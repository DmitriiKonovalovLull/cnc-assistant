"""
МИНИМАЛЬНЫЙ Telegram-бот для Дня 1.
Следует строго спецификации: ❌ Без FSM, ❌ Без логики расчета
Только: принять текст → передать в handle_message → отправить ответ
"""

import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler as TGMessageHandler, Filters, CallbackContext

from core.handler import MessageHandler as CoreMessageHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация обработчика
core_handler = CoreMessageHandler()


def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start."""
    user = update.effective_user

    welcome = (
        "🟢 **ДЕНЬ 1 — ФУНДАМЕНТ «МОЗГА» БОТА**\n\n"
        "🎯 **Что я умею:**\n"
        "• Понимать контекст разговора\n"
        "• Делать предположения (как ИИ)\n"
        "• Давать понятные советы по обработке\n"
        "• Не зацикливаться на вопросах\n\n"
        "**Просто напиши, что делаешь:**\n"
        "▸ `токарю алюминий`\n"
        "▸ `фрезерую сталь 45`\n"
        "▸ `сверлю титан черновое`\n\n"
        "Я попробую понять и помочь!"
    )

    update.message.reply_text(welcome, parse_mode='Markdown')


def handle_text(update: Update, context: CallbackContext) -> None:
    """Обработчик ВСЕХ текстовых сообщений."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    logger.info(f"User {user_id}: '{text}'")

    try:
        # Обрабатываем сообщение
        response = core_handler.handle_message(user_id, text)

        # Отправляем ответ
        update.message.reply_text(response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Ошибка обработки: {e}", exc_info=True)
        update.message.reply_text(
            "⚠️ Произошла ошибка обработки. Попробуйте еще раз или /start"
        )


def reset(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /reset."""
    from core.context import reset_context
    user_id = update.effective_user.id
    reset_context(user_id)

    update.message.reply_text(
        "🔄 Контекст сброшен. Начинаем новый диалог!\n\n"
        "Что будем обрабатывать?"
    )


def help_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /help."""
    help_text = (
        "🤖 **CNC Assistant - День 1**\n\n"
        "**Как работать:**\n"
        "1. Опиши задачу (материал + операция)\n"
        "2. Я задам уточняющие вопросы\n"
        "3. Попроси совет когда нужно\n\n"
        "**Примеры диалога:**\n"
        "• Ты: `алюминий токарка`\n"
        "• Я: предположу черновую, спрошу режим\n"
        "• Ты: `чистовая`\n"
        "• Я: запомню, буду ждать команду\n"
        "• Ты: `совет`\n"
        "• Я: дам рекомендации\n\n"
        "**Команды:**\n"
        "▸ /start — начать\n"
        "▸ /reset — сбросить контекст\n"
        "▸ /help — справка\n"
        "▸ /status — показать контекст\n\n"
        "💡 Я учусь на ваших ответах!"
    )

    update.message.reply_text(help_text, parse_mode='Markdown')


def status_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /status."""
    from core.context import get_context
    user_id = update.effective_user.id
    context = get_context(user_id)

    status_text = (
        "📊 **Текущий контекст:**\n"
        f"• Материал: {context.material or 'не указан'}\n"
        f"• Операция: {context.operation or 'не указана'}\n"
        f"• Инструмент: {context.tool or 'не указан'}\n"
        f"• Режим: {context.mode or 'не указан'}\n\n"
        f"Сообщений в истории: {len(context.messages)}"
    )

    update.message.reply_text(status_text, parse_mode='Markdown')


def main() -> None:
    """Запуск бота."""
    # ТОКЕН БОТА (ЗАМЕНИТЕ НА СВОЙ!)
    TOKEN = os.getenv("TELEGRAM_TOKEN", "8201932079:AAEUMoy2E22jUAUGZghGmOMPTDRrLAIfBh8")

    if "YOUR_BOT_TOKEN" in TOKEN:
        print("❌ ОШИБКА: Замените токен в коде!")
        print(f"Текущий токен: {TOKEN}")
        return

    print("=" * 60)
    print("🟢 ДЕНЬ 1 — ФУНДАМЕНТ «МОЗГА» БОТА")
    print("=" * 60)
    print("✅ Без расчётов | ✅ Без LLM | ✅ Только логика")
    print(f"🤖 Запускаю бота...")
    print("=" * 60)

    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Регистрация обработчиков
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("reset", reset))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("status", status_command))

    # Обработчик текстовых сообщений
    dispatcher.add_handler(TGMessageHandler(Filters.text & ~Filters.command, handle_text))

    # Запуск
    print("✅ Бот запущен! Ожидаю сообщений...")
    print("=" * 60)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()