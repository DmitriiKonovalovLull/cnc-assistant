"""
🤖 Telegram бот - День 1 (упрощенная версия)
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Получаем токен
TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TOKEN or TOKEN == 'your_bot_token_here':
    logger.error("❌ TELEGRAM_TOKEN не найден в .env файле!")
    logger.error("Добавьте ваш токен в .env файл")
    exit(1)

print(f"🤖 Запуск бота с токеном: {TOKEN[:10]}...")

# Импортируем библиотеку telegram
try:
    from telegram import Update
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
except ImportError:
    logger.error("❌ python-telegram-bot не установлен!")
    logger.error("Установите: pip install python-telegram-bot")
    exit(1)


# Простой обработчик сообщений для Дня 1
class SimpleHandler:
    """Упрощенный обработчик для Дня 1."""

    def __init__(self):
        self.user_contexts = {}
        logger.info("🤖 Простой обработчик инициализирован")

    def handle_message(self, user_id, text):
        """Обрабатывает сообщение пользователя."""
        text_lower = text.lower().strip()

        # Проверяем команды
        if text_lower == '/start':
            return self._handle_start(user_id)
        elif text_lower == '/help':
            return self._handle_help()
        elif text_lower == '/reset':
            return self._handle_reset(user_id)

        # Обрабатываем запросы на обработку
        if any(word in text_lower for word in ['токар', 'фрезер', 'расточ', 'сверл']):
            return self._handle_processing_request(user_id, text_lower)
        elif any(word in text_lower for word in ['посчитай', 'расчет', 'режим']):
            return self._handle_calculation_request(user_id, text_lower)
        elif any(word in text_lower for word in ['алюмин', 'сталь', 'титан']):
            return self._handle_material_request(user_id, text_lower)

        # Общий ответ
        return (
            "🤔 Понял, что вы хотите что-то обработать, но мне нужно больше информации.\n\n"
            "💡 **Примеры запросов:**\n"
            "• `токарка алюминия диаметр 50`\n"
            "• `фрезеровка стали 45`\n"
            "• `посчитай режимы для титана`\n\n"
            "📚 **Команды:** /start /help /reset"
        )

    def _handle_start(self, user_id):
        """Обрабатывает команду /start."""
        self.user_contexts[user_id] = {"step": "waiting_material"}

        return (
            f"👋 Привет! Я CNC Assistant.\n\n"
            f"🎯 Помогаю с настройкой станков ЧПУ.\n\n"
            f"💡 **Просто расскажите что делаете:**\n"
            f"• `токарка алюминия диаметр 50`\n"
            f"• `фрезеровка стали 45`\n"
            f"• `черновая обработка титана`\n\n"
            f"🧠 **Я:**\n"
            f"• Запоминаю ваши предпочтения\n"
            f"• Учусь на исправлениях\n"
            f"• Становлюсь точнее со временем\n\n"
            f"Что обрабатываем?"
        )

    def _handle_help(self):
        """Обрабатывает команду /help."""
        return (
            "🆘 **Помощь по использованию:**\n\n"
            "🤖 **Как работает бот:**\n"
            "1. Вы описываете задачу\n"
            "2. Я задаю уточняющие вопросы\n"
            "3. Даю рекомендации\n"
            "4. Учусь на ваших исправлениях\n\n"
            "💡 **Примеры запросов:**\n"
            "• `токарка алюминия диаметр 50`\n"
            "• `фрезеровка стали 45 чистовая`\n"
            "• `посчитай для титана`\n\n"
            "🔄 **Исправления:**\n"
            "• `нет, подача 0.3 слишком большая`\n"
            "• `исправь скорость на 150`\n"
            "• `это много, сделай 0.2`\n\n"
            "📊 **Команды:**\n"
            "/start - начало работы\n"
            "/reset - новый диалог\n"
            "/help - эта справка"
        )

    def _handle_reset(self, user_id):
        """Обрабатывает команду /reset."""
        self.user_contexts[user_id] = {"step": "waiting_material"}
        return "🔄 Начинаем новую задачу! Какой материал обрабатываем?"

    def _handle_processing_request(self, user_id, text):
        """Обрабатывает запрос на обработку."""
        # Определяем материал
        material = None
        if 'алюмин' in text:
            material = "алюминий"
        elif 'сталь' in text:
            material = "сталь"
        elif 'титан' in text:
            material = "титан"

        # Определяем операцию
        operation = None
        if 'токар' in text:
            operation = "токарная обработка"
        elif 'фрезер' in text:
            operation = "фрезерование"
        elif 'расточ' in text:
            operation = "расточка"
        elif 'сверл' in text:
            operation = "сверление"

        # Ищем диаметр
        import re
        diameter_match = re.search(r'диаметр\s*(\d+)', text)
        diameter = diameter_match.group(1) if diameter_match else None

        # Формируем ответ
        response_parts = ["✅ Понял запрос:"]

        if material:
            response_parts.append(f"• **Материал:** {material}")
        if operation:
            response_parts.append(f"• **Операция:** {operation}")
        if diameter:
            response_parts.append(f"• **Диаметр:** Ø{diameter} мм")

        response_parts.append("\n🎯 **Рекомендации:**")

        # Простые рекомендации
        if material == "алюминий":
            if operation == "токарная обработка":
                response_parts.append("• Скорость резания: 250-350 м/мин")
                response_parts.append("• Подача: 0.2-0.4 мм/об")
            elif operation == "фрезерование":
                response_parts.append("• Скорость резания: 300-400 м/мин")
                response_parts.append("• Подача на зуб: 0.1-0.2 мм")

        elif material == "сталь":
            if operation == "токарная обработка":
                response_parts.append("• Скорость резания: 80-150 м/мин")
                response_parts.append("• Подача: 0.1-0.3 мм/об")
            elif operation == "фрезерование":
                response_parts.append("• Скорость резания: 60-120 м/мин")
                response_parts.append("• Подача на зуб: 0.08-0.15 мм")

        response_parts.append("\n💡 **Если параметры не подходят — просто скажите!**")

        return "\n".join(response_parts)

    def _handle_calculation_request(self, user_id, text):
        """Обрабатывает запрос на расчет."""
        return (
            "🧮 **Запрос на расчет получен!**\n\n"
            "Для точного расчета мне нужно знать:\n"
            "• Материал (алюминий, сталь, титан)\n"
            "• Операцию (токарка, фрезеровка)\n"
            "• Диаметр обработки\n\n"
            "💡 **Примеры:**\n"
            "• `посчитай для алюминия токарка диаметр 50`\n"
            "• `расчет стали 45 фрезеровка`\n"
            "• `режимы для титана диаметр 80`"
        )

    def _handle_material_request(self, user_id, text):
        """Обрабатывает запрос только с материалом."""
        if 'алюмин' in text:
            material = "алюминий"
        elif 'сталь' in text:
            material = "сталь"
        elif 'титан' in text:
            material = "титан"
        else:
            material = "материал"

        return (
            f"✅ Вижу, что вы работаете с **{material}**!\n\n"
            f"Теперь скажите:\n"
            f"• Какая операция? (токарка, фрезеровка, расточка)\n"
            f"• Какой диаметр?\n"
            f"• Черновая или чистовая обработка?\n\n"
            f"💡 **Пример:** `токарка диаметр 50 черновая`"
        )


# Создаем обработчик
handler = SimpleHandler()


# Обработчики для Telegram
def start_command(update: Update, context: CallbackContext) -> None:
    """Обрабатывает команду /start."""
    user_id = str(update.effective_user.id)
    response = handler.handle_message(user_id, "/start")
    update.message.reply_text(response, parse_mode='Markdown')


def help_command(update: Update, context: CallbackContext) -> None:
    """Обрабатывает команду /help."""
    user_id = str(update.effective_user.id)
    response = handler.handle_message(user_id, "/help")
    update.message.reply_text(response, parse_mode='Markdown')


def reset_command(update: Update, context: CallbackContext) -> None:
    """Обрабатывает команду /reset."""
    user_id = str(update.effective_user.id)
    response = handler.handle_message(user_id, "/reset")
    update.message.reply_text(response, parse_mode='Markdown')


def handle_message(update: Update, context: CallbackContext) -> None:
    """Обрабатывает текстовые сообщения."""
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    logger.info(f"Сообщение от {user_id}: {text}")

    try:
        response = handler.handle_message(user_id, text)
        update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}")
        update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте еще раз или используйте /start",
            parse_mode='Markdown'
        )


def main() -> None:
    """Запускает бота."""
    try:
        # Создаем Updater и передаем ему токен
        updater = Updater(TOKEN, use_context=True)

        # Получаем диспетчер для регистрации обработчиков
        dispatcher = updater.dispatcher

        # Регистрируем обработчики команд
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("reset", reset_command))

        # Регистрируем обработчик текстовых сообщений
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

        # Запускаем бота
        updater.start_polling()

        logger.info("✅ Бот запущен и готов к работе!")
        logger.info("📱 Откройте Telegram и найдите вашего бота")
        logger.info("💬 Напишите /start чтобы начать")

        # Запускаем бота до прерывания Ctrl+C
        updater.idle()

    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        logger.error("Проверьте:")
        logger.error("1. Правильность токена")
        logger.error("2. Интернет-соединение")
        logger.error("3. Что бот создан через @BotFather")


if __name__ == '__main__':
    main()