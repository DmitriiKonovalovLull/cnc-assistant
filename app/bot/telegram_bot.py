"""
Telegram-бот для сбора данных о режимах резания.
Основной источник данных для будущего ML.
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional

# Дополнительные импорты для работы с .env
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.state_machine import UserState, get_next_state, update_user_data
from app.services.recommendation import calculate_cutting_modes
from app.services.experience import calculate_deviation_score
from app.storage.memory import save_interaction
from app.bot.prompts import get_random_question

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация - загрузка из .env файла
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Берём токен из переменной окружения

# Проверка токена
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
    logger.error("Токен не найден! Убедитесь, что в .env файле есть TELEGRAM_TOKEN")
    raise ValueError("Токен бота не найден в .env файле")

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ... остальной код остается без изменений ...

# Клавиатура для быстрого ввода материалов
materials_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="сталь"), KeyboardButton(text="алюминий")],
        [KeyboardButton(text="титан"), KeyboardButton(text="нержавейка")],
        [KeyboardButton(text="чугун"), KeyboardButton(text="латунь")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# Клавиатура для операций
operations_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="токарка"), KeyboardButton(text="фрезерование")],
        [KeyboardButton(text="сверление"), KeyboardButton(text="растачивание")],
    ],
    resize_keyboard=True
)

# Клавиатура для режимов
mode_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="черновой"), KeyboardButton(text="чистовой")],
        [KeyboardButton(text="получистовой")],
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Начало диалога."""
    await state.set_state(UserState.waiting_material)
    await message.answer(
        "Привет! Я помощник по подбору режимов резания.\n"
        "Для обучения ИИ мне нужно собирать данные о реальных решениях.\n\n"
        "Выбери материал:",
        reply_markup=materials_kb
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь."""
    help_text = (
        "Я помогаю подбирать режимы резания и собираю данные для обучения ИИ.\n\n"
        "Команды:\n"
        "/start - начать подбор режимов\n"
        "/data - посмотреть собранные данные (разработчикам)\n"
        "/help - эта справка\n\n"
        "Ваши решения сохраняются анонимно для улучшения рекомендаций."
    )
    await message.answer(help_text)


@dp.message(Command("data"))
async def cmd_data(message: Message):
    """Показать статистику по собранным данным (только для разработчиков)."""
    # Здесь можно добавить вывод статистики
    await message.answer(
        "Функция статистики в разработке.\n"
        "Сейчас идёт сбор данных: материал → операция → режим → диаметр → рекомендация → ваше решение."
    )


@dp.message()
async def handle_message(message: Message, state: FSMContext):
    """Основной обработчик сообщений с FSM."""
    user_id = message.from_user.id
    text = message.text.strip().lower()
    current_state = await state.get_state()

    # Получаем текущие данные пользователя
    user_data = await state.get_data()

    # Определяем следующее состояние и обновляем данные
    next_state, updated_data = await get_next_state(
        current_state, text, user_data
    )

    # Сохраняем обновлённые данные
    await state.set_data(updated_data)

    # Переводим в следующее состояние
    if next_state:
        await state.set_state(next_state)

    # Отправляем ответ в зависимости от состояния
    if next_state == UserState.waiting_material:
        await message.answer("Выбери материал:", reply_markup=materials_kb)

    elif next_state == UserState.waiting_operation:
        await message.answer(
            f"Материал: {updated_data.get('material')}\n"
            "Выбери операцию:",
            reply_markup=operations_kb
        )

    elif next_state == UserState.waiting_mode:
        await message.answer(
            f"Материал: {updated_data.get('material')}\n"
            f"Операция: {updated_data.get('operation')}\n"
            "Выбери режим обработки:",
            reply_markup=mode_kb
        )

    elif next_state == UserState.waiting_diameter:
        await message.answer(
            f"Материал: {updated_data.get('material')}\n"
            f"Операция: {updated_data.get('operation')}\n"
            f"Режим: {updated_data.get('mode')}\n\n"
            "Введи диаметр обработки в мм (например: 50 или 300):"
        )

    elif next_state == UserState.waiting_recommendation:
        # Рассчитываем рекомендации
        material = updated_data.get('material')
        operation = updated_data.get('operation')
        mode = updated_data.get('mode')
        diameter = float(updated_data.get('diameter', 0))

        try:
            recommendations = calculate_cutting_modes(
                material=material,
                operation=operation,
                mode=mode,
                diameter=diameter
            )

            # Сохраняем рекомендации
            updated_data['recommendation'] = recommendations
            await state.set_data(updated_data)

            # Формируем ответ
            response = (
                f"📊 Рекомендации:\n"
                f"Материал: {material}\n"
                f"Операция: {operation}\n"
                f"Режим: {mode}\n"
                f"Диаметр: {diameter} мм\n\n"
                f"Скорость резания (Vc): {recommendations.get('vc', 0)} м/мин\n"
                f"Обороты (n): {recommendations.get('rpm', 0)} об/мин\n"
                f"Подача (f): {recommendations.get('feed', 0)} мм/об\n\n"
                f"Какие обороты ВЫ ставите на станке?\n"
                f"(Введи число, например: {int(recommendations.get('rpm', 0) * 0.8)} или {int(recommendations.get('rpm', 0) * 1.2)})"
            )

            await message.answer(response)

        except Exception as e:
            logger.error(f"Error calculating recommendations: {e}")
            await message.answer(
                "Ошибка расчёта. Попробуй снова /start"
            )
            await state.clear()

    elif next_state == UserState.waiting_user_choice:
        # Пользователь ввёл свои обороты
        try:
            user_rpm = float(text)
            recommendations = updated_data.get('recommendation', {})
            recommended_rpm = recommendations.get('rpm', 0)

            if recommended_rpm > 0:
                # Рассчитываем отклонение
                deviation_score = calculate_deviation_score(
                    user_rpm=user_rpm,
                    recommended_rpm=recommended_rpm
                )

                # Сохраняем взаимодействие в базу
                interaction_data = {
                    'user_id': user_id,
                    'material': updated_data.get('material'),
                    'operation': updated_data.get('operation'),
                    'mode': updated_data.get('mode'),
                    'diameter': updated_data.get('diameter'),
                    'recommended_rpm': recommended_rpm,
                    'recommended_vc': recommendations.get('vc'),
                    'user_rpm': user_rpm,
                    'deviation_score': deviation_score,
                    'context': {
                        'machine_type': 'unknown',  # Можно спросить позже
                        'strategy': 'fixed_rpm' if abs(deviation_score) > 0.3 else 'adaptive'
                    }
                }

                save_interaction(interaction_data)

                # Иногда задаём вопросы для сбора контекста
                if deviation_score > 0.5 or deviation_score < -0.5:
                    question = get_random_question()
                    await message.answer(
                        f"Спасибо! Данные сохранены.\n\n"
                        f"Отклонение от рекомендации: {deviation_score:.1%}\n\n"
                        f"{question}"
                    )
                else:
                    await message.answer(
                        f"Спасибо! Данные сохранены.\n"
                        f"Отклонение от рекомендации: {deviation_score:.1%}"
                    )

                # Сбрасываем состояние
                await state.clear()

                # Предлагаем начать заново
                await message.answer(
                    "Хочешь подобрать ещё режимы? Нажми /start",
                    reply_markup=types.ReplyKeyboardRemove()
                )

            else:
                await message.answer("Ошибка данных. Попробуй /start")
                await state.clear()

        except ValueError:
            await message.answer("Пожалуйста, введи число (обороты в минуту):")

    else:
        await message.answer(
            "Не понимаю. Нажми /start чтобы начать подбор режимов."
        )


async def start_telegram_bot():
    """Запуск Telegram бота."""
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot failed: {e}")
    finally:
        await bot.session.close()
