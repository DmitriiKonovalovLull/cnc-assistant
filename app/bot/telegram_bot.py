"""
Telegram-бот для сбора РЕШЕНИЙ операторов.
Версия 5.0: Новая философия - сбор практики, а не рекомендаций.
Использует: core/calculator.py, core/pass_strategy.py, storage/models.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import re

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

# Наши новые модули
from app.core.calculator import (
    CuttingCalculator, CuttingLimits, MaterialProperties,
    ToolProperties, Geometry, create_calculator_from_context,
    validate_recommendation_against_limits
)
from app.core.pass_strategy import (
    PassStrategy, StrategyConfig, create_strategy_from_context,
    format_strategy_for_user, validate_strategy_against_practice
)
from app.storage.models import (
    save_user_decision, get_user_decisions, create_decision_id,
    init_orm_database, get_session
)

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Создаем директорию для логов
logs_dir = Path(__file__).parent.parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)


# ============================================================================
# СОСТОЯНИЯ ДЛЯ НОВОЙ ЛОГИКИ
# ============================================================================

class CNCStates(StatesGroup):
    """Состояния для сбора решений операторов."""
    # Контекст
    waiting_material = State()
    waiting_operation = State()
    waiting_machine_type = State()
    waiting_machine_power = State()

    # Геометрия
    waiting_diameter_start = State()
    waiting_diameter_end = State()
    waiting_length = State()

    # Инструмент
    waiting_tool_material = State()
    waiting_tool_radius = State()
    waiting_tool_overhang = State()

    # Рекомендация и сравнение
    waiting_recommendation_view = State()  # показываем рекомендацию
    waiting_comparison_rpm = State()  # спрашиваем про обороты
    waiting_comparison_feed = State()  # спрашиваем про подачу
    waiting_comparison_ap = State()  # спрашиваем про глубину

    # Ручной ввод (если выбрано)
    waiting_manual_rpm = State()
    waiting_manual_feed = State()
    waiting_manual_ap = State()

    # Подтверждение
    waiting_confirmation = State()


# ============================================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(logs_dir / "cnc_bot_v5.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ БОТА
# ============================================================================

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
    logger.error("❌ Токен не найден! Проверьте .env файл")
    print("❌ ОШИБКА: Токен бота не найден!")
    print("❌ Проверьте файл .env и установите TELEGRAM_TOKEN")
    sys.exit(1)

# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация базы данных
try:
    init_orm_database()
    logger.info("✅ База данных инициализирована")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации БД: {e}")


# ============================================================================
# КЛАВИАТУРЫ ДЛЯ НОВОГО ДИАЛОГА
# ============================================================================

def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню."""
    builder = ReplyKeyboardBuilder()

    builder.add(KeyboardButton(text="🎯 Новый подбор"))
    builder.add(KeyboardButton(text="📊 Мои решения"))
    builder.add(KeyboardButton(text="📚 База знаний"))
    builder.add(KeyboardButton(text="❓ Помощь"))

    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)


def create_material_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора материала."""
    builder = ReplyKeyboardBuilder()

    materials = [
        "Сталь", "Алюминий", "Нержавейка",
        "Чугун", "Титан", "Латунь", "Медь"
    ]

    for material in materials:
        builder.add(KeyboardButton(text=material))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 2, 1)

    return builder.as_markup(resize_keyboard=True)


def create_operation_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора операции."""
    builder = ReplyKeyboardBuilder()

    operations = [
        "Черновая", "Получистовая", "Чистовая",
        "Проточка", "Растачивание"
    ]

    for op in operations:
        builder.add(KeyboardButton(text=op))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 1)

    return builder.as_markup(resize_keyboard=True)


def create_machine_type_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора типа станка."""
    builder = ReplyKeyboardBuilder()

    machines = [
        "Токарный ЧПУ", "Токарный ручной",
        "Фрезерный ЧПУ", "Фрезерный ручной"
    ]

    for machine in machines:
        builder.add(KeyboardButton(text=machine))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 1)

    return builder.as_markup(resize_keyboard=True)


def create_power_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора мощности станка."""
    builder = ReplyKeyboardBuilder()

    powers = ["7.5", "11", "15", "18.5", "22", "30", "45"]

    for power in powers:
        builder.add(KeyboardButton(text=f"{power} кВт"))

    builder.add(KeyboardButton(text="Другая..."))
    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(3, 3, 1, 1)

    return builder.as_markup(resize_keyboard=True)


def create_tool_material_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора материала инструмента."""
    builder = ReplyKeyboardBuilder()

    materials = [
        "Твердый сплав", "Быстрорез",
        "Керамика", "CBN", "Другое"
    ]

    for material in materials:
        builder.add(KeyboardButton(text=material))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 1)

    return builder.as_markup(resize_keyboard=True)


def create_tool_radius_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора радиуса пластины."""
    builder = ReplyKeyboardBuilder()

    radii = ["0.4", "0.6", "0.8", "1.0", "1.2", "1.6", "2.0", "2.4"]

    for radius in radii:
        builder.add(KeyboardButton(text=f"{radius} мм"))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(3, 3, 3)

    return builder.as_markup(resize_keyboard=True)


def create_comparison_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для сравнения с рекомендацией."""
    builder = InlineKeyboardBuilder()

    builder.add(types.InlineKeyboardButton(
        text="⬇️ Ниже",
        callback_data="comparison_lower"
    ))
    builder.add(types.InlineKeyboardButton(
        text="✅ Так же",
        callback_data="comparison_same"
    ))
    builder.add(types.InlineKeyboardButton(
        text="⬆️ Выше",
        callback_data="comparison_higher"
    ))
    builder.add(types.InlineKeyboardButton(
        text="✏️ Вручную",
        callback_data="comparison_manual"
    ))

    builder.adjust(2, 2)
    return builder.as_markup()


def create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения сохранения."""
    builder = InlineKeyboardBuilder()

    builder.add(types.InlineKeyboardButton(
        text="💾 Сохранить решение",
        callback_data="save_decision"
    ))
    builder.add(types.InlineKeyboardButton(
        text="🔄 Начать заново",
        callback_data="restart"
    ))

    builder.adjust(1)
    return builder.as_markup()


# ============================================================================
# ФОРМАТИРОВАНИЕ СООБЩЕНИЙ
# ============================================================================

def format_welcome_message(name: str) -> str:
    """Форматировать приветственное сообщение."""
    return (
        f"👋 Привет, {name}!\n\n"
        f"🤖 <b>Я - CNC Assistant v5.0</b>\n\n"
        f"<b>Новая философия:</b>\n"
        f"• 📊 <b>Я НЕ даю истину</b> - я собираю практику\n"
        f"• 🧠 <b>Ваши решения</b> обучают будущего ИИ-технолога\n"
        f"• ⚖️ <b>Сравниваю</b> рекомендации с реальностью\n\n"
        f"<i>Давайте соберем ваш опыт для обучения ИИ!</i>"
    )


def format_context_summary(context: Dict[str, Any]) -> str:
    """Форматировать сводку контекста."""
    lines = []

    lines.append("📋 <b>СВОДКА КОНТЕКСТА:</b>")
    lines.append("")
    lines.append(f"• <b>Материал:</b> {context.get('material', 'не указан')}")
    lines.append(f"• <b>Операция:</b> {context.get('operation', 'не указана')}")

    if 'machine_type' in context:
        lines.append(f"• <b>Станок:</b> {context.get('machine_type')}")

    if 'machine_power' in context:
        lines.append(f"• <b>Мощность:</b> {context.get('machine_power')} кВт")

    if 'diameter_start' in context and 'diameter_end' in context:
        lines.append(f"• <b>Диаметры:</b> {context.get('diameter_start')} → {context.get('diameter_end')} мм")
        stock = (context.get('diameter_start', 0) - context.get('diameter_end', 0)) / 2
        lines.append(f"• <b>Припуск:</b> {stock:.1f} мм на сторону")

    if 'length' in context:
        lines.append(f"• <b>Длина:</b> {context.get('length')} мм")

    if 'tool_material' in context:
        lines.append(f"• <b>Инструмент:</b> {context.get('tool_material')}")

    if 'tool_radius' in context:
        lines.append(f"• <b>Радиус пластины:</b> {context.get('tool_radius')} мм")

    return "\n".join(lines)


def format_recommendation_with_strategy(
        recommendation: Dict[str, Any],
        strategy: Dict[str, Any],
        context: Dict[str, Any]
) -> str:
    """Форматировать рекомендацию со стратегией проходов."""
    lines = []

    lines.append("🎯 <b>РЕКОМЕНДАЦИЯ (ТАБЛИЧНЫЕ ЗНАЧЕНИЯ):</b>")
    lines.append("")

    # Основные параметры
    lines.append(f"• <b>Скорость резания:</b> {recommendation.get('vc', 0):.1f} м/мин")
    lines.append(f"• <b>Обороты:</b> {recommendation.get('rpm', 0):.0f} об/мин")
    lines.append(f"• <b>Подача:</b> {recommendation.get('feed', 0):.3f} мм/об")
    lines.append(f"• <b>Глубина резания:</b> {recommendation.get('ap', 0):.2f} мм")
    lines.append(f"• <b>Расчетная мощность:</b> {recommendation.get('power_kw', 0):.1f} кВт")
    lines.append("")

    # Стратегия проходов
    lines.append("📊 <b>СТРАТЕГИЯ ПРОХОДОВ:</b>")
    lines.append(f"• <b>Тип операции:</b> {strategy.get('operation_type', 'черновая')}")
    lines.append(f"• <b>Количество проходов:</b> {strategy.get('total_passes', 1)}")
    lines.append(f"• <b>Средняя глубина:</b> {strategy.get('avg_ap_mm', 0):.2f} мм")
    lines.append("")

    # Ключевое сообщение
    lines.append("<i>📌 На практике операторы часто корректируют эти параметры</i>")
    lines.append("<i>   в зависимости от конкретных условий, инструмента и опыта.</i>")
    lines.append("")

    # Предупреждения
    warnings = recommendation.get('warnings', []) + strategy.get('warnings', [])
    if warnings:
        lines.append("⚠️ <b>ВНИМАНИЕ:</b>")
        for warning in warnings[:3]:  # показываем не более 3 предупреждений
            lines.append(f"• {warning}")
        lines.append("")

    return "\n".join(lines)


def format_comparison_prompt(
        parameter: str,
        recommended_value: float,
        unit: str
) -> str:
    """Форматировать запрос на сравнение."""
    param_names = {
        "rpm": ("обороты шпинделя", "об/мин"),
        "feed": ("подачу на оборот", "мм/об"),
        "ap": ("глубину резания", "мм")
    }

    name, actual_unit = param_names.get(parameter, (parameter, unit))

    return (
        f"<b>Сравнение: {name}</b>\n\n"
        f"🎯 <b>Табличная рекомендация:</b> {recommended_value:.1f} {actual_unit}\n\n"
        f"<i>А какие {name} ВЫ используете на практике?</i>\n"
        f"• ⬇️ <b>Ниже</b> рекомендации?\n"
        f"• ✅ <b>Примерно так же</b>?\n"
        f"• ⬆️ <b>Выше</b> рекомендации?\n"
        f"• ✏️ Хочу <b>ввести своё значение</b>"
    )


def format_decision_result(
        recommendation: Dict[str, Any],
        user_values: Dict[str, float],
        comparison_choices: Dict[str, str]
) -> str:
    """Форматировать результат решения."""
    lines = []

    lines.append("📋 <b>ВАШЕ РЕШЕНИЕ СОХРАНЕНО!</b>")
    lines.append("")

    lines.append("<b>Сравнение с табличными значениями:</b>")
    lines.append("<code>Параметр     | Таблица | Вы | Отношение</code>")
    lines.append("<code>" + "-" * 45 + "</code>")

    for param in ["rpm", "feed", "ap"]:
        rec_val = recommendation.get(param, 0)
        user_val = user_values.get(param, 0)

        if rec_val > 0:
            ratio = user_val / rec_val

            if ratio < 0.9:
                icon = "⬇️"
            elif ratio > 1.1:
                icon = "⬆️"
            else:
                icon = "✅"

            # Форматируем значения
            if param == "rpm":
                rec_str = f"{rec_val:.0f}"
                user_str = f"{user_val:.0f}"
                param_name = "Обороты"
            elif param == "feed":
                rec_str = f"{rec_val:.3f}"
                user_str = f"{user_val:.3f}"
                param_name = "Подача"
            else:  # ap
                rec_str = f"{rec_val:.2f}"
                user_str = f"{user_val:.2f}"
                param_name = "Глубина"

            lines.append(f"<code>{param_name:12} | {rec_str:7} | {user_str:4} | {icon} {ratio:.2f}x</code>")

    lines.append("")
    lines.append("<i>🧠 Это решение будет использовано для обучения ИИ-технолога.</i>")
    lines.append("<i>Спасибо за ваш опыт!</i>")

    return "\n".join(lines)


# ============================================================================
# УТИЛИТЫ ДЛЯ ОБРАБОТКИ ВВОДА
# ============================================================================

class InputParser:
    """Парсер ввода пользователя."""

    @staticmethod
    def parse_number(text: str) -> Optional[float]:
        """Парсить число из текста."""
        try:
            # Убираем все нецифровые символы, кроме точки и запятой
            clean_text = ''.join(c for c in text if c.isdigit() or c in ',.')

            if not clean_text:
                return None

            # Заменяем запятую на точку
            clean_text = clean_text.replace(',', '.')

            # Берем первое число
            import re
            match = re.search(r'\d+(?:\.\d+)?', clean_text)
            if match:
                return float(match.group())

            return None
        except:
            return None

    @staticmethod
    def parse_diameter(text: str) -> Optional[float]:
        """Парсить диаметр."""
        value = InputParser.parse_number(text)
        if value and 0.1 <= value <= 2000:
            return value
        return None

    @staticmethod
    def parse_power(text: str) -> Optional[float]:
        """Парсить мощность."""
        value = InputParser.parse_number(text)
        if value and 1 <= value <= 500:
            return value
        return None

    @staticmethod
    def parse_length(text: str) -> Optional[float]:
        """Парсить длину."""
        value = InputParser.parse_number(text)
        if value and 1 <= value <= 5000:
            return value
        return None

    @staticmethod
    def parse_overhang(text: str) -> Optional[float]:
        """Парсить вылет инструмента."""
        value = InputParser.parse_number(text)
        if value and 10 <= value <= 500:
            return value
        return None


# ============================================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================================

@dp.message(Command("start", "help"))
async def cmd_start(message: Message, state: FSMContext):
    """Начало работы с ботом."""
    await state.clear()

    await message.answer(
        format_welcome_message(message.from_user.first_name or "друг"),
        reply_markup=create_main_menu_keyboard()
    )
    logger.info(f"Пользователь {message.from_user.id} начал работу")


@dp.message(F.text == "🎯 Новый подбор")
async def start_new_selection(message: Message, state: FSMContext):
    """Начать новый подбор."""
    await state.clear()
    await state.set_state(CNCStates.waiting_material)

    await message.answer(
        "🔧 <b>НОВЫЙ ПОДБОР РЕЖИМОВ</b>\n\n"
        "<i>Цель: собрать ваше РЕАЛЬНОЕ решение для обучения ИИ.</i>\n\n"
        "1️⃣ Выберите материал заготовки:",
        reply_markup=create_material_keyboard()
    )


@dp.message(F.text == "📊 Мои решения")
async def show_my_decisions(message: Message):
    """Показать решения пользователя."""
    user_id = str(message.from_user.id)

    try:
        with get_session() as session:
            decisions = get_user_decisions(session, user_id, limit=10)

            if not decisions:
                await message.answer(
                    "📊 <b>Ваши решения:</b>\n\n"
                    "У вас пока нет сохраненных решений.\n"
                    "Начните новый подбор, чтобы собрать данные для ИИ!",
                    reply_markup=create_main_menu_keyboard()
                )
                return

            lines = []
            lines.append("📊 <b>ПОСЛЕДНИЕ РЕШЕНИЯ:</b>")
            lines.append("")

            for i, decision in enumerate(decisions[:5], 1):
                date = decision.timestamp.strftime("%d.%m") if decision.timestamp else "??.??"
                material = decision.bot_vc_m_min  # временно, пока нет поля material

                lines.append(
                    f"{i}. {date} | Материал: {material} | "
                    f"Ø: {decision.diameter_start_mm:.0f}→{decision.diameter_end_mm:.0f} мм"
                )

            lines.append("")
            lines.append(f"<i>Всего решений: {len(decisions)}</i>")
            lines.append("<i>Каждое решение улучшает ИИ-технолога!</i>")

            await message.answer("\n".join(lines))

    except Exception as e:
        logger.error(f"Ошибка получения решений: {e}")
        await message.answer(
            "❌ <b>Ошибка загрузки данных</b>\n\n"
            "Попробуйте позже или начните новый подбор.",
            reply_markup=create_main_menu_keyboard()
        )


@dp.message(F.text == "📚 База знаний")
async def show_knowledge_base(message: Message):
    """Показать базу знаний."""
    text = (
        "📚 <b>БАЗА ЗНАНИЙ CNC ASSISTANT</b>\n\n"

        "<b>🎯 Философия проекта:</b>\n"
        "Мы НЕ даем «правильные» ответы. Мы собираем РЕАЛЬНУЮ ПРАКТИКУ "
        "операторов для обучения будущего ИИ-технолога.\n\n"

        "<b>🧠 Как это работает:</b>\n"
        "1. Вы вводите параметры обработки\n"
        "2. Бот показывает табличные значения\n"
        "3. Вы указываете, КАК ДЕЛАЕТЕ НА ПРАКТИКЕ\n"
        "4. Разница сохраняется как данные для ИИ\n\n"

        "<b>📊 Что мы собираем:</b>\n"
        "• Разницу между таблицами и практикой\n"
        "• Адаптацию операторов к разным условиям\n"
        "• Реальные физические ограничения\n\n"

        "<b>🚀 Цель:</b>\n"
        "Создать ИИ-технолога, который понимает не только теорию, "
        "но и реальные условия производства."
    )

    await message.answer(text)


@dp.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    """Показать справку."""
    help_text = (
        "❓ <b>ПОМОЩЬ И FAQ</b>\n\n"

        "<b>🤔 Зачем этот бот?</b>\n"
        "Чтобы собрать РЕАЛЬНЫЕ данные о том, как работают практики, "
        "а не теоретические рекомендации.\n\n"

        "<b>🔧 Как проходит диалог?</b>\n"
        "1. Выбираете материал, операцию, станок\n"
        "2. Вводите геометрические параметры\n"
        "3. Получаете табличные рекомендации\n"
        "4. Сравниваете с вашей практикой\n"
        "5. Сохраняете решение для обучения ИИ\n\n"

        "<b>🎯 Что делать, если не знаю точных значений?</b>\n"
        "• Используйте примерные значения\n"
        "• Выбирайте «Так же» или «Вручную»\n"
        "• Важен сам факт сравнения\n\n"

        "<b>⚠️ Важно понимать:</b>\n"
        "Бот НЕ даёт инструкций к действию! "
        "Он только собирает данные о различиях между теорией и практикой."
    )

    await message.answer(help_text)


@dp.message(F.text == "🔙 Назад")
async def handle_back(message: Message, state: FSMContext):
    """Обработка кнопки Назад."""
    current_state = await state.get_state()

    if not current_state:
        await message.answer(
            "🔙 Возвращаемся в главное меню",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Маппинг возвратов
    back_map = {
        CNCStates.waiting_material: None,  # в главное меню
        CNCStates.waiting_operation: CNCStates.waiting_material,
        CNCStates.waiting_machine_type: CNCStates.waiting_operation,
        CNCStates.waiting_machine_power: CNCStates.waiting_machine_type,
        CNCStates.waiting_diameter_start: CNCStates.waiting_machine_power,
        CNCStates.waiting_diameter_end: CNCStates.waiting_diameter_start,
        CNCStates.waiting_length: CNCStates.waiting_diameter_end,
        CNCStates.waiting_tool_material: CNCStates.waiting_length,
        CNCStates.waiting_tool_radius: CNCStates.waiting_tool_material,
        CNCStates.waiting_tool_overhang: CNCStates.waiting_tool_radius,
        CNCStates.waiting_recommendation_view: CNCStates.waiting_tool_overhang,
    }

    next_state = back_map.get(current_state)

    if next_state is None:
        # Возврат в главное меню
        await state.clear()
        await message.answer(
            "🔙 Возвращаемся в главное меню",
            reply_markup=create_main_menu_keyboard()
        )
    else:
        await state.set_state(next_state)
        await message.answer(
            "🔙 Возвращаемся на предыдущий шаг",
            reply_markup=await _get_keyboard_for_state(next_state)
        )


# ============================================================================
# ОСНОВНОЙ ДИАЛОГ: СБОР КОНТЕКСТА
# ============================================================================

@dp.message(CNCStates.waiting_material)
async def handle_material(message: Message, state: FSMContext):
    """Обработка выбора материала."""
    material = message.text

    if material == "🔙 Назад":
        await handle_back(message, state)
        return

    await state.update_data(material=material)
    await state.set_state(CNCStates.waiting_operation)

    await message.answer(
        f"✅ Материал: <b>{material}</b>\n\n"
        f"2️⃣ Выберите тип операции:",
        reply_markup=create_operation_keyboard()
    )


@dp.message(CNCStates.waiting_operation)
async def handle_operation(message: Message, state: FSMContext):
    """Обработка выбора операции."""
    operation = message.text

    if operation == "🔙 Назад":
        await handle_back(message, state)
        return

    await state.update_data(operation=operation)
    await state.set_state(CNCStates.waiting_machine_type)

    await message.answer(
        f"✅ Операция: <b>{operation}</b>\n\n"
        f"3️⃣ Выберите тип станка:",
        reply_markup=create_machine_type_keyboard()
    )


@dp.message(CNCStates.waiting_machine_type)
async def handle_machine_type(message: Message, state: FSMContext):
    """Обработка выбора типа станка."""
    machine_type = message.text

    if machine_type == "🔙 Назад":
        await handle_back(message, state)
        return

    await state.update_data(machine_type=machine_type)
    await state.set_state(CNCStates.waiting_machine_power)

    # Определяем мощность по умолчанию
    default_power = "15 кВт" if "ЧПУ" in machine_type else "7.5 кВт"

    await message.answer(
        f"✅ Станок: <b>{machine_type}</b>\n\n"
        f"4️⃣ Выберите мощность станка:",
        reply_markup=create_power_keyboard()
    )


@dp.message(CNCStates.waiting_machine_power)
async def handle_machine_power(message: Message, state: FSMContext):
    """Обработка выбора мощности."""
    text = message.text

    if text == "🔙 Назад":
        await handle_back(message, state)
        return

    if text == "Другая...":
        await message.answer(
            "Введите мощность станка в кВт (например: 7.5, 11, 15):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 Назад")]],
                resize_keyboard=True
            )
        )
        return

    power = None
    if "кВт" in text:
        # Извлекаем число из текста
        parser = InputParser()
        power = parser.parse_power(text)

    if power is None:
        await message.answer(
            "❌ Неверный формат мощности. Введите число в кВт (например: 15, 7.5):"
        )
        return

    await state.update_data(machine_power=power)
    await state.set_state(CNCStates.waiting_diameter_start)

    await message.answer(
        f"✅ Мощность: <b>{power} кВт</b>\n\n"
        f"5️⃣ Введите начальный диаметр заготовки (мм):\n"
        f"<i>Например: 100, 50.5, 200</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Назад")]],
            resize_keyboard=True
        )
    )


@dp.message(CNCStates.waiting_diameter_start)
async def handle_diameter_start(message: Message, state: FSMContext):
    """Обработка начального диаметра."""
    text = message.text

    if text == "🔙 Назад":
        await handle_back(message, state)
        return

    parser = InputParser()
    diameter = parser.parse_diameter(text)

    if diameter is None:
        await message.answer(
            "❌ Неверный формат диаметра. Введите число в мм (например: 100, 50.5):"
        )
        return

    await state.update_data(diameter_start=diameter)
    await state.set_state(CNCStates.waiting_diameter_end)

    await message.answer(
        f"✅ Начальный диаметр: <b>{diameter} мм</b>\n\n"
        f"6️⃣ Введите конечный диаметр (мм):\n"
        f"<i>Меньше начального. Например: 90, 45, 180</i>"
    )


@dp.message(CNCStates.waiting_diameter_end)
async def handle_diameter_end(message: Message, state: FSMContext):
    """Обработка конечного диаметра."""
    text = message.text

    if text == "🔙 Назад":
        await handle_back(message, state)
        return

    parser = InputParser()
    diameter = parser.parse_diameter(text)

    if diameter is None:
        await message.answer(
            "❌ Неверный формат диаметра. Введите число в мм:"
        )
        return

    # Получаем начальный диаметр
    data = await state.get_data()
    start_diameter = data.get('diameter_start', 0)

    if diameter >= start_diameter:
        await message.answer(
            "❌ Конечный диаметр должен быть МЕНЬШЕ начального!\n"
            f"Начальный: {start_diameter} мм\n"
            "Введите правильное значение:"
        )
        return

    await state.update_data(diameter_end=diameter)
    await state.set_state(CNCStates.waiting_length)

    stock = (start_diameter - diameter) / 2
    await message.answer(
        f"✅ Конечный диаметр: <b>{diameter} мм</b>\n"
        f"📏 Припуск: <b>{stock:.1f} мм</b> на сторону\n\n"
        f"7️⃣ Введите длину обработки (мм):\n"
        f"<i>Например: 50, 100, 200</i>"
    )


@dp.message(CNCStates.waiting_length)
async def handle_length(message: Message, state: FSMContext):
    """Обработка длины обработки."""
    text = message.text

    if text == "🔙 Назад":
        await handle_back(message, state)
        return

    parser = InputParser()
    length = parser.parse_length(text)

    if length is None:
        await message.answer(
            "❌ Неверный формат длины. Введите число в мм (например: 100, 50):"
        )
        return

    await state.update_data(length=length)
    await state.set_state(CNCStates.waiting_tool_material)

    await message.answer(
        f"✅ Длина обработки: <b>{length} мм</b>\n\n"
        f"8️⃣ Выберите материал инструмента:",
        reply_markup=create_tool_material_keyboard()
    )


@dp.message(CNCStates.waiting_tool_material)
async def handle_tool_material(message: Message, state: FSMContext):
    """Обработка материала инструмента."""
    tool_material = message.text

    if tool_material == "🔙 Назад":
        await handle_back(message, state)
        return

    await state.update_data(tool_material=tool_material)
    await state.set_state(CNCStates.waiting_tool_radius)

    await message.answer(
        f"✅ Материал инструмента: <b>{tool_material}</b>\n\n"
        f"9️⃣ Выберите радиус пластины:",
        reply_markup=create_tool_radius_keyboard()
    )


@dp.message(CNCStates.waiting_tool_radius)
async def handle_tool_radius(message: Message, state: FSMContext):
    """Обработка радиуса пластины."""
    text = message.text

    if text == "🔙 Назад":
        await handle_back(message, state)
        return

    parser = InputParser()
    radius = parser.parse_number(text)

    if radius is None or radius <= 0:
        await message.answer(
            "❌ Неверный формат радиуса. Выберите из списка или введите число:"
        )
        return

    await state.update_data(tool_radius=radius)
    await state.set_state(CNCStates.waiting_tool_overhang)

    await message.answer(
        f"✅ Радиус пластины: <b>{radius} мм</b>\n\n"
        f"🔟 Введите вылет инструмента (мм):\n"
        f"<i>Рекомендуется 30-50 мм. Например: 30, 40, 50</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Назад")]],
            resize_keyboard=True
        )
    )


@dp.message(CNCStates.waiting_tool_overhang)
async def handle_tool_overhang(message: Message, state: FSMContext):
    """Обработка вылета инструмента."""
    text = message.text

    if text == "🔙 Назад":
        await handle_back(message, state)
        return

    parser = InputParser()
    overhang = parser.parse_overhang(text)

    if overhang is None:
        await message.answer(
            "❌ Неверный формат вылета. Введите число в мм (30-100 мм):"
        )
        return

    await state.update_data(tool_overhang=overhang)

    # Показываем сводку контекста
    data = await state.get_data()

    await message.answer(
        format_context_summary(data),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="✅ Рассчитать")]],
            resize_keyboard=True
        )
    )

    # Устанавливаем состояние просмотра рекомендаций
    await state.set_state(CNCStates.waiting_recommendation_view)


@dp.message(CNCStates.waiting_recommendation_view)
async def handle_recommendation_view(message: Message, state: FSMContext):
    """Обработка просмотра рекомендаций."""
    text = message.text

    if text == "🔙 Назад":
        await handle_back(message, state)
        return

    if text != "✅ Рассчитать":
        await message.answer("Нажмите «Рассчитать» для продолжения или «Назад» для возврата")
        return

    # Рассчитываем рекомендации
    await _calculate_and_show_recommendations(message, state)


async def _calculate_and_show_recommendations(message: Message, state: FSMContext):
    """Рассчитать и показать рекомендации."""
    data = await state.get_data()

    try:
        # 1. Создаем калькулятор
        calculator = _create_calculator_from_data(data)

        # 2. Получаем рекомендацию
        operation_type = _map_operation_type(data.get('operation', ''))
        recommendation = calculator.get_recommendation(operation_type)

        # 3. Создаем стратегию проходов
        strategy = _create_strategy_from_data(data, recommendation)

        # 4. Сохраняем в состояние
        await state.update_data(
            recommendation=recommendation,
            strategy=strategy,
            calculator_context=data
        )

        # 5. Показываем пользователю
        await message.answer(
            format_recommendation_with_strategy(recommendation, strategy, data),
            reply_markup=types.ReplyKeyboardRemove()
        )

        # 6. Начинаем сравнение с оборотами
        await _start_comparison(message, state, "rpm")

    except Exception as e:
        logger.error(f"Ошибка расчета: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Ошибка расчета рекомендаций</b>\n\n"
            f"Причина: {str(e)}\n\n"
            "Пожалуйста, начните заново.",
            reply_markup=create_main_menu_keyboard()
        )
        await state.clear()


def _create_calculator_from_data(data: Dict[str, Any]) -> CuttingCalculator:
    """Создать калькулятор из данных."""
    # Ограничения
    limits = CuttingLimits(
        max_power_kw=data.get('machine_power', 15.0),
        max_rpm=3000.0,
        max_ap_by_tool_mm=6.0,
        max_feed_by_tool_mm_rev=0.4,
        max_tool_overhang_mm=100.0
    )

    # Материал
    material = MaterialProperties(
        material_type=_map_material_type(data.get('material', 'сталь')),
        hardness_hb=None,
        tensile_strength_mpa=None
    )

    # Инструмент
    tool = ToolProperties(
        insert_material=_map_tool_material(data.get('tool_material', 'твердый сплав')),
        insert_radius_mm=data.get('tool_radius', 0.8),
        tool_overhang_mm=data.get('tool_overhang', 30.0)
    )

    # Геометрия
    geometry = Geometry(
        diameter_start_mm=data.get('diameter_start', 100.0),
        diameter_end_mm=data.get('diameter_end', 90.0),
        length_mm=data.get('length', 50.0),
        is_external=True
    )

    return CuttingCalculator(limits, material, tool, geometry)


def _create_strategy_from_data(data: Dict[str, Any], recommendation: Dict[str, Any]) -> Dict[str, Any]:
    """Создать стратегию из данных."""
    config = StrategyConfig(
        operation_type=_map_operation_type(data.get('operation', 'черновая')),
        is_external=True,
        max_ap_rough_mm=min(6.0, recommendation.get('ap', 4.0))
    )

    strategy = PassStrategy(
        diameter_start_mm=data.get('diameter_start', 100.0),
        diameter_end_mm=data.get('diameter_end', 90.0),
        config=config
    )

    return strategy.generate_strategy()


def _map_material_type(material: str) -> str:
    """Сопоставить материал."""
    material = material.lower()

    if any(x in material for x in ["алюмин", "alum"]):
        return "aluminum"
    elif any(x in material for x in ["нержавей", "нерж", "stainless"]):
        return "stainless_steel"
    elif any(x in material for x in ["титан", "titan"]):
        return "titanium"
    elif any(x in material for x in ["чугун", "cast"]):
        return "cast_iron"
    elif any(x in material for x in ["латунь", "медь", "brass", "copper"]):
        return "copper"
    else:
        return "steel"


def _map_operation_type(operation: str) -> str:
    """Сопоставить тип операции."""
    operation = operation.lower()

    if any(x in operation for x in ["чист", "finish"]):
        return "finishing"
    elif any(x in operation for x in ["получист", "semi"]):
        return "semi_finishing"
    else:
        return "roughing"


def _map_tool_material(tool_material: str) -> str:
    """Сопоставить материал инструмента."""
    tool_material = tool_material.lower()

    if any(x in tool_material for x in ["тверд", "carbide"]):
        return "carbide"
    elif any(x in tool_material for x in ["быстр", "hss"]):
        return "hss"
    elif any(x in tool_material for x in ["керам", "ceramic"]):
        return "ceramic"
    elif any(x in tool_material for x in ["cbn", "нитрид"]):
        return "cbn"
    else:
        return "carbide"


# ============================================================================
# СРАВНЕНИЕ С РЕКОМЕНДАЦИЕЙ
# ============================================================================

async def _start_comparison(message: Message, state: FSMContext, parameter: str):
    """Начать сравнение параметра."""
    data = await state.get_data()
    recommendation = data.get('recommendation', {})

    units = {
        "rpm": "об/мин",
        "feed": "мм/об",
        "ap": "мм"
    }

    await message.answer(
        format_comparison_prompt(
            parameter,
            recommendation.get(parameter, 0),
            units.get(parameter, "")
        ),
        reply_markup=create_comparison_keyboard()
    )

    # Устанавливаем соответствующее состояние
    state_map = {
        "rpm": CNCStates.waiting_comparison_rpm,
        "feed": CNCStates.waiting_comparison_feed,
        "ap": CNCStates.waiting_comparison_ap
    }

    await state.set_state(state_map.get(parameter))


@dp.callback_query(F.data.startswith("comparison_"))
async def handle_comparison_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора сравнения."""
    choice = callback.data.replace("comparison_", "")

    # Определяем текущий параметр из состояния
    current_state = await state.get_state()

    param_map = {
        CNCStates.waiting_comparison_rpm: "rpm",
        CNCStates.waiting_comparison_feed: "feed",
        CNCStates.waiting_comparison_ap: "ap"
    }

    parameter = param_map.get(current_state)

    if not parameter:
        await callback.answer("Ошибка определения параметра")
        return

    data = await state.get_data()
    recommendation = data.get('recommendation', {})

    if choice == "manual":
        # Переходим к ручному вводу
        state_map = {
            "rpm": CNCStates.waiting_manual_rpm,
            "feed": CNCStates.waiting_manual_feed,
            "ap": CNCStates.waiting_manual_ap
        }

        await state.set_state(state_map.get(parameter))

        units = {
            "rpm": "об/мин",
            "feed": "мм/об",
            "ap": "мм"
        }

        await callback.message.answer(
            f"✏️ <b>Ручной ввод {parameter}:</b>\n\n"
            f"Табличное значение: {recommendation.get(parameter, 0):.1f} {units.get(parameter, '')}\n\n"
            f"Введите ваше значение:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 К сравнению")]],
                resize_keyboard=True
            )
        )

    else:
        # Автоматический расчет значения на основе выбора
        recommended_value = recommendation.get(parameter, 0)

        if choice == "lower":
            user_value = recommended_value * 0.8
        elif choice == "higher":
            user_value = recommended_value * 1.2
        else:  # same
            user_value = recommended_value

        # Сохраняем значение
        current_values = data.get('user_values', {})
        current_values[parameter] = user_value

        current_choices = data.get('comparison_choices', {})
        current_choices[parameter] = choice

        await state.update_data(
            user_values=current_values,
            comparison_choices=current_choices
        )

        await callback.answer(f"Сохранено: {user_value:.1f}")

        # Переходим к следующему параметру
        await _proceed_to_next_parameter(callback.message, state, parameter)

    await callback.answer()


async def _proceed_to_next_parameter(message: types.Message, state: FSMContext, current_param: str):
    """Перейти к следующему параметру."""
    parameters = ["rpm", "feed", "ap"]

    try:
        current_idx = parameters.index(current_param)

        if current_idx < len(parameters) - 1:
            # Есть следующий параметр
            next_param = parameters[current_idx + 1]
            await _start_comparison(message, state, next_param)
        else:
            # Все параметры собраны - показываем сводку
            await _show_decision_summary(message, state)

    except ValueError:
        # Неизвестный параметр
        await _show_decision_summary(message, state)


# ============================================================================
# РУЧНОЙ ВВОД
# ============================================================================

@dp.message(
    CNCStates.waiting_manual_rpm |
    CNCStates.waiting_manual_feed |
    CNCStates.waiting_manual_ap
)
async def handle_manual_input(message: Message, state: FSMContext):
    """Обработка ручного ввода."""
    text = message.text

    if text == "🔙 К сравнению":
        # Возвращаемся к сравнению
        current_state = await state.get_state()

        param_map = {
            CNCStates.waiting_manual_rpm: "rpm",
            CNCStates.waiting_manual_feed: "feed",
            CNCStates.waiting_manual_ap: "ap"
        }

        parameter = param_map.get(current_state)
        if parameter:
            await _start_comparison(message, state, parameter)
        return

    parser = InputParser()
    value = parser.parse_number(text)

    if value is None:
        await message.answer("❌ Неверный формат. Введите число:")
        return

    # Определяем параметр из состояния
    current_state = await state.get_state()

    param_map = {
        CNCStates.waiting_manual_rpm: "rpm",
        CNCStates.waiting_manual_feed: "feed",
        CNCStates.waiting_manual_ap: "ap"
    }

    parameter = param_map.get(current_state)

    if not parameter:
        await message.answer("❌ Ошибка определения параметра")
        return

    # Сохраняем значение
    data = await state.get_data()

    current_values = data.get('user_values', {})
    current_values[parameter] = value

    current_choices = data.get('comparison_choices', {})
    current_choices[parameter] = "manual"

    await state.update_data(
        user_values=current_values,
        comparison_choices=current_choices
    )

    await message.answer(
        f"✅ Сохранено: {value}",
        reply_markup=types.ReplyKeyboardRemove()
    )

    # Переходим к следующему параметру
    await _proceed_to_next_parameter(message, state, parameter)


# ============================================================================
# ПОДТВЕРЖДЕНИЕ И СОХРАНЕНИЕ
# ============================================================================

async def _show_decision_summary(message: types.Message, state: FSMContext):
    """Показать сводку решения."""
    data = await state.get_data()

    recommendation = data.get('recommendation', {})
    user_values = data.get('user_values', {})
    comparison_choices = data.get('comparison_choices', {})

    # Заполняем недостающие значения значениями по умолчанию
    for param in ["rpm", "feed", "ap"]:
        if param not in user_values:
            user_values[param] = recommendation.get(param, 0)
        if param not in comparison_choices:
            comparison_choices[param] = "same"

    await state.update_data(
        user_values=user_values,
        comparison_choices=comparison_choices
    )

    await message.answer(
        format_decision_result(recommendation, user_values, comparison_choices),
        reply_markup=create_confirmation_keyboard()
    )

    await state.set_state(CNCStates.waiting_confirmation)


@dp.callback_query(F.data == "save_decision")
async def handle_save_decision(callback: types.CallbackQuery, state: FSMContext):
    """Сохранить решение."""
    try:
        data = await state.get_data()
        user_id = str(callback.from_user.id)

        # Подготавливаем данные для сохранения
        decision_data = {
            'user_id': user_id,
            'geometry': {
                'diameter_start_mm': data.get('diameter_start', 0),
                'diameter_end_mm': data.get('diameter_end', 0),
                'length_mm': data.get('length', 50.0),
            },
            'operation': {
                'operation_type': data.get('operation', 'черновая'),
                'is_external': True,
            },
            'bot_recommendation': {
                'vc': data.get('recommendation', {}).get('vc', 0),
                'rpm': data.get('recommendation', {}).get('rpm', 0),
                'feed': data.get('recommendation', {}).get('feed', 0),
                'ap': data.get('recommendation', {}).get('ap', 0),
                'power_kw': data.get('recommendation', {}).get('power_kw', 0),
                'passes_strategy': data.get('strategy', {}).get('passes', []),
                'total_passes': data.get('strategy', {}).get('total_passes', 1),
            },
            'user_actual': {
                'rpm': data.get('user_values', {}).get('rpm', 0),
                'feed': data.get('user_values', {}).get('feed', 0),
                'ap': data.get('user_values', {}).get('ap', 0),
                'comparison_choice': _get_overall_choice(data.get('comparison_choices', {})),
            },
            'source': 'telegram',
            'session_id': f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'full_context': {
                'user_data': data,
                'timestamp': datetime.now().isoformat()
            }
        }

        # Сохраняем в БД
        with get_session() as session:
            decision = save_user_decision(
                session=session,
                user_id=user_id,
                geometry=decision_data['geometry'],
                operation=decision_data['operation'],
                bot_recommendation=decision_data['bot_recommendation'],
                user_actual=decision_data['user_actual'],
                comparison_choice=decision_data['user_actual']['comparison_choice'],
                source=decision_data['source'],
                session_id=decision_data['session_id'],
                full_context=decision_data['full_context']
            )

        await callback.message.answer(
            "✅ <b>Решение успешно сохранено!</b>\n\n"
            "<i>Этот опыт будет использован для обучения ИИ-технолога.</i>\n\n"
            "Спасибо за ваш вклад! 🧠",
            reply_markup=create_main_menu_keyboard()
        )

        await state.clear()
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка сохранения решения: {e}", exc_info=True)
        await callback.message.answer(
            "❌ <b>Ошибка сохранения</b>\n\n"
            "Попробуйте еще раз или начните заново.",
            reply_markup=create_main_menu_keyboard()
        )
        await state.clear()
        await callback.answer()


@dp.callback_query(F.data == "restart")
async def handle_restart(callback: types.CallbackQuery, state: FSMContext):
    """Начать заново."""
    await state.clear()
    await callback.message.answer(
        "🔄 Начинаем новый подбор!",
        reply_markup=create_main_menu_keyboard()
    )
    await callback.answer()


def _get_overall_choice(comparison_choices: Dict[str, str]) -> str:
    """Получить общий выбор на основе всех сравнений."""
    if not comparison_choices:
        return "manual"

    # Подсчитываем голоса
    from collections import Counter
    counter = Counter(comparison_choices.values())

    # Если есть manual - возвращаем manual
    if "manual" in counter:
        return "manual"

    # Возвращаем самый частый выбор
    return counter.most_common(1)[0][0]


async def _get_keyboard_for_state(state: State) -> Optional[ReplyKeyboardMarkup]:
    """Получить клавиатуру для состояния."""
    if state == CNCStates.waiting_material:
        return create_material_keyboard()
    elif state == CNCStates.waiting_operation:
        return create_operation_keyboard()
    elif state == CNCStates.waiting_machine_type:
        return create_machine_type_keyboard()
    elif state == CNCStates.waiting_machine_power:
        return create_power_keyboard()
    elif state == CNCStates.waiting_tool_material:
        return create_tool_material_keyboard()
    elif state == CNCStates.waiting_tool_radius:
        return create_tool_radius_keyboard()

    return None


# ============================================================================
# ЗАПУСК БОТА
# ============================================================================

async def start_telegram_bot():
    """Запуск Telegram бота."""
    try:
        # Получаем информацию о боте
        me = await bot.get_me()

        print("\n" + "=" * 60)
        print(f"🤖 Запуск CNC Assistant v5.0")
        print(f"📝 Бот: @{me.username}")
        print(f"🎯 Философия: сбор РЕАЛЬНОЙ ПРАКТИКИ операторов")
        print(f"🧠 Цель: обучение ИИ-технолога на реальных данных")
        print(f"⚙️ Модули: calculator.py, pass_strategy.py, storage/models.py")
        print(f"💾 База данных: storage/cnc.db")
        print("=" * 60 + "\n")

        logger.info(f"Запуск бота: @{me.username}")

        # Удаляем вебхук
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Вебхук удален")

        # Запускаем polling
        print("🔄 Бот запущен и ожидает сообщений...")
        print("⚠️ Для остановки нажмите Ctrl+C\n")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=True
        )

    except KeyboardInterrupt:
        print("\n👋 Остановка бота...")
        logger.info("Остановка бота по запросу пользователя")
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта")


def main():
    """Основная функция запуска."""
    print("🚀 CNC Assistant Telegram Bot v5.0")
    print("🎯 НОВАЯ ФИЛОСОФИЯ: сбор практики, а не рекомендаций")
    print("🧠 Использует: core/calculator.py, core/pass_strategy.py, storage/models.py")
    print("⚡ Загрузка конфигурации...")

    try:
        asyncio.run(start_telegram_bot())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Фатальная ошибка: {e}")
        logger.error(f"Фатальная ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()