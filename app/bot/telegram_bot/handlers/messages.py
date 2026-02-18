"""
Основной обработчик текстовых сообщений.
"""

from aiogram import Dispatcher
from aiogram import types
from aiogram.fsm.context import FSMContext

from app.bot.telegram_bot.utils import get_user_context, _looks_like_experience_feedback
from app.bot.telegram_bot.main import handler, rate_limiter, metrics
from app.bot.context_manager import split_long_message, format_for_device
import time

# Заглушка - полная реализация будет в следующем этапе
# Из-за большого объема кода (более 1000 строк обработки сообщений)
# этот модуль будет создан отдельно


def register_message_handlers(dp: Dispatcher):
    """Зарегистрировать обработчики сообщений."""
    dp.message.register(handle_message)
    
    # TODO: Реализовать полную обработку сообщений из telegram_bot.py
    # Это включает:
    # - Проверку специальных состояний (переименование работы)
    # - Проверку приветствий
    # - Проверку команд
    # - Обработку опыта оператора
    # - Основную обработку через handler
    # - Маршрутизацию по action
    pass


async def handle_message(message: types.Message, state: FSMContext):
    """Главный обработчик всех текстовых сообщений."""
    start_time = time.time()
    
    user_id = str(message.from_user.id)
    user_text = (message.text or "").strip()
    
    # Rate limiting (используем async версию)
    if rate_limiter:
        is_allowed = await rate_limiter.is_allowed(user_id)
        if not is_allowed:
            remaining_time = await rate_limiter.get_remaining_time(user_id)
            await message.answer(
                f"⏳ <b>Слишком много сообщений</b>\n\n"
                f"Пожалуйста, подождите {int(remaining_time)} секунд перед отправкой следующего сообщения."
            )
            return
    
    # Обновляем метрики
    metrics.total_messages += 1
    
    try:
        # TODO: Реализовать полную логику обработки сообщений
        # Временно используем старый обработчик
        pass
    
    except Exception as e:
        from app.bot.telegram_bot.main import logger
        logger.error(f"Error handling message: {e}", exc_info=True)
        metrics.total_errors += 1
        await message.answer(
            f"❌ <b>Произошла ошибка</b>\n\n"
            f"Попробуйте описать задачу заново или нажмите /start"
        )
    finally:
        # Обновляем метрики времени ответа
        response_time = time.time() - start_time
        metrics.add_response_time(response_time)
