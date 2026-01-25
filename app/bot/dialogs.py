"""
Диалоги для сбора РЕШЕНИЙ операторов.
Главное: бот спрашивает "А как вы делаете на практике?" с кнопками выбора.
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from app.core.calculator import CuttingCalculator, create_calculator_from_context
from app.core.pass_strategy import PassStrategy, create_strategy_from_context
from app.domain.models import (
    MachineSpecs, MaterialData, ToolData, GeometryData,
    OperationData, BotRecommendation, UserActual,
    UserDecisionRecord, create_record_id
)


# ============================================================================
# КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ============================================================================

@dataclass
class DialogConfig:
    """Конфигурация диалогов."""
    # Тексты
    ask_experience_level: bool = True
    ask_machine_details: bool = True
    ask_tool_details: bool = True
    show_alternative_strategies: bool = True

    # Поведение
    always_show_warnings: bool = True
    enable_manual_input: bool = True
    collect_comments: bool = True

    # Лимиты
    max_diameter_mm: float = 1000.0
    min_diameter_mm: float = 0.1
    max_stock_mm: float = 50.0  # максимальный припуск на сторону


# ============================================================================
# КЛАВИАТУРЫ ДЛЯ ДИАЛОГА
# ============================================================================

def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню."""
    builder = ReplyKeyboardBuilder()

    builder.add(KeyboardButton(text="🎯 Подбор режимов"))
    builder.add(KeyboardButton(text="📊 Мои решения"))
    builder.add(KeyboardButton(text="⚙️ Настройки"))
    builder.add(KeyboardButton(text="❓ Помощь"))

    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)


def create_experience_level_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора уровня опыта."""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(
        text="👶 Начинающий (< 1 года)",
        callback_data="experience_beginner"
    ))
    builder.add(InlineKeyboardButton(
        text="👨‍🏭 Опытный (1-5 лет)",
        callback_data="experience_intermediate"
    ))
    builder.add(InlineKeyboardButton(
        text="👴 Эксперт (> 5 лет)",
        callback_data="experience_expert"
    ))
    builder.add(InlineKeyboardButton(
        text="🤷 Не знаю",
        callback_data="experience_unknown"
    ))

    builder.adjust(1)
    return builder.as_markup()


def create_material_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора материала."""
    builder = ReplyKeyboardBuilder()

    # Основные материалы
    materials = [
        "Сталь", "Алюминий", "Нержавейка",
        "Титан", "Чугун", "Латунь", "Медь"
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
        "Проточка", "Растачивание", "Резьба"
    ]

    for op in operations:
        builder.add(KeyboardButton(text=op))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 2)

    return builder.as_markup(resize_keyboard=True)


def create_machine_type_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора типа станка."""
    builder = ReplyKeyboardBuilder()

    machines = [
        "Токарный ЧПУ", "Токарный ручной",
        "Фрезерный ЧПУ", "Фрезерный ручной",
        "Токарно-фрезерный"
    ]

    for machine in machines:
        builder.add(KeyboardButton(text=machine))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 1)

    return builder.as_markup(resize_keyboard=True)


def create_power_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора мощности станка."""
    builder = ReplyKeyboardBuilder()

    # Типичные мощности станков (кВт)
    powers = ["7.5", "11", "15", "18.5", "22", "30", "45", "55"]

    for power in powers:
        builder.add(KeyboardButton(text=f"{power} кВт"))

    builder.add(KeyboardButton(text="Другая..."))
    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(3, 3, 2, 1)

    return builder.as_markup(resize_keyboard=True)


def create_tool_material_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора материала пластины."""
    builder = ReplyKeyboardBuilder()

    materials = [
        "Твердый сплав", "Быстрорез", "Керамика",
        "CBN", "Алмаз", "Не знаю"
    ]

    for material in materials:
        builder.add(KeyboardButton(text=material))

    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 2)

    return builder.as_markup(resize_keyboard=True)


def create_comparison_keyboard() -> InlineKeyboardMarkup:
    """
    ГЛАВНАЯ КЛАВИАТУРА - сравнение с рекомендацией.
    Бот спрашивает: "А как вы делаете на практике?"
    """
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(
        text="⬇️ Ниже рекомендации",
        callback_data="comparison_lower"
    ))
    builder.add(InlineKeyboardButton(
        text="✅ Примерно так же",
        callback_data="comparison_same"
    ))
    builder.add(InlineKeyboardButton(
        text="⬆️ Выше рекомендации",
        callback_data="comparison_higher"
    ))
    builder.add(InlineKeyboardButton(
        text="✏️ Введу вручную",
        callback_data="comparison_manual"
    ))

    builder.adjust(2, 2)
    return builder.as_markup()


def create_manual_input_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для ручного ввода параметров."""
    builder = ReplyKeyboardBuilder()

    builder.add(KeyboardButton(text="🔙 К сравнению"))
    builder.add(KeyboardButton(text="🏁 Завершить"))

    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения сохранения."""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(
        text="💾 Сохранить решение",
        callback_data="save_decision"
    ))
    builder.add(InlineKeyboardButton(
        text="🔄 Начать заново",
        callback_data="restart"
    ))
    builder.add(InlineKeyboardButton(
        text="📊 Посмотреть детали",
        callback_data="show_details"
    ))

    builder.adjust(1)
    return builder.as_markup()


# ============================================================================
# ФОРМАТИРОВАНИЕ СООБЩЕНИЙ
# ============================================================================

def format_calculator_warnings(warnings: List[str]) -> str:
    """Форматировать предупреждения калькулятора."""
    if not warnings:
        return ""

    lines = ["⚠️ <b>Внимание:</b>"]
    for warning in warnings:
        lines.append(f"• {warning}")

    return "\n".join(lines)


def format_recommendation_message(
        recommendation: Dict[str, Any],
        context: Dict[str, Any]
) -> str:
    """
    Форматировать сообщение с рекомендацией.
    Ключевая фраза: "Я бы рекомендовал... Но на практике операторы часто ставят..."
    """
    lines = []

    # Заголовок
    lines.append("🎯 <b>РЕКОМЕНДАЦИЯ ПО РЕЖИМАМ РЕЗАНИЯ</b>")
    lines.append("")

    # Контекст
    lines.append(f"<b>Материал:</b> {context.get('material', 'не указан')}")
    lines.append(f"<b>Операция:</b> {context.get('operation', 'не указана')}")
    lines.append(f"<b>Диаметр:</b> {context.get('diameter', 0):.1f} мм")
    lines.append(f"<b>Припуск:</b> {context.get('stock_per_side', 0):.1f} мм на сторону")
    lines.append("")

    # Основные параметры
    lines.append("<b>Основные параметры:</b>")
    lines.append(f"• Скорость резания: {recommendation.get('vc', 0):.1f} м/мин")
    lines.append(f"• Обороты шпинделя: {recommendation.get('rpm', 0):.0f} об/мин")
    lines.append(f"• Подача: {recommendation.get('feed', 0):.3f} мм/об")
    lines.append(f"• Глубина резания: {recommendation.get('ap', 0):.2f} мм")
    lines.append(f"• Мощность: {recommendation.get('power_kw', 0):.1f} кВт")
    lines.append("")

    # Стратегия проходов
    strategy = recommendation.get('passes_strategy', {})
    if strategy:
        lines.append(f"<b>Стратегия:</b> {strategy.get('operation_type', 'черновая')}")
        lines.append(f"<b>Количество проходов:</b> {strategy.get('total_passes', 1)}")
        lines.append("")

    # Ключевое сообщение
    lines.append("<i>📌 На практике операторы часто корректируют эти параметры</i>")
    lines.append("<i>   в зависимости от конкретных условий, инструмента и опыта.</i>")
    lines.append("")

    # Вопрос
    lines.append("<b>❓ А какие параметры ВЫ используете на практике?</b>")

    # Предупреждения
    warnings = recommendation.get('warnings', [])
    if warnings:
        lines.append("")
        lines.append(format_calculator_warnings(warnings))

    return "\n".join(lines)


def format_comparison_question(
        recommendation: Dict[str, Any],
        parameter: str = "rpm"
) -> str:
    """
    Форматировать вопрос для сравнения.

    Args:
        parameter: "rpm", "feed", или "ap"
    """
    param_names = {
        "rpm": ("обороты", "об/мин"),
        "feed": ("подачу", "мм/об"),
        "ap": ("глубину резания", "мм")
    }

    name, unit = param_names.get(parameter, ("параметр", ""))
    value = recommendation.get(parameter, 0)

    return (
        f"<b>Сравнение по {name}:</b>\n\n"
        f"🎯 <b>Рекомендация:</b> {value:.1f} {unit}\n\n"
        f"<i>А вы на практике используете:</i>\n"
        f"• <b>Меньше</b> рекомендации?\n"
        f"• <b>Примерно так же</b>?\n"
        f"• <b>Больше</b> рекомендации?\n"
        f"• Или хотите <b>ввести своё значение</b>?"
    )


def format_manual_input_prompt(
        recommendation: Dict[str, Any],
        parameter: str = "rpm"
) -> str:
    """Запрос на ручной ввод параметра."""
    param_names = {
        "rpm": ("обороты шпинделя", "об/мин"),
        "feed": ("подачу на оборот", "мм/об"),
        "ap": ("глубину резания", "мм")
    }

    name, unit = param_names.get(parameter, ("параметр", ""))
    recommended = recommendation.get(parameter, 0)

    return (
        f"✏️ <b>Ручной ввод {name}:</b>\n\n"
        f"🎯 Рекомендация: {recommended:.1f} {unit}\n\n"
        f"Введите ваше значение в {unit}:\n"
        f"<i>(например: {recommended * 0.8:.0f}, {recommended:.0f}, {recommended * 1.2:.0f})</i>"
    )


def format_decision_summary(
        recommendation: Dict[str, Any],
        user_values: Dict[str, float],
        comparison: str
) -> str:
    """Форматировать сводку решения оператора."""
    lines = []

    lines.append("📋 <b>СВОДКА ВАШЕГО РЕШЕНИЯ</b>")
    lines.append("")

    # Таблица сравнения
    lines.append("<b>Параметр     | Рекомендация | Ваш выбор | Отношение</b>")
    lines.append("-" * 50)

    for param in ["rpm", "feed", "ap"]:
        rec_val = recommendation.get(param, 0)
        user_val = user_values.get(param, 0)

        if rec_val > 0 and user_val > 0:
            ratio = user_val / rec_val
            ratio_str = f"{ratio:.2f}x"

            # Иконка отношения
            if ratio < 0.9:
                icon = "⬇️"
            elif ratio > 1.1:
                icon = "⬆️"
            else:
                icon = "✅"

            # Форматирование значений
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

            lines.append(f"{param_name:12} | {rec_str:12} | {user_str:9} | {icon} {ratio_str}")

    lines.append("")

    # Интерпретация
    lines.append("<b>Интерпретация:</b>")

    if comparison == "lower":
        lines.append("📉 Вы используете <b>более консервативные</b> параметры")
        lines.append("   (меньшая нагрузка на инструмент, более безопасно)")
    elif comparison == "same":
        lines.append("✅ Ваши параметры <b>близки к рекомендациям</b>")
        lines.append("   (стандартный подход для данных условий)")
    elif comparison == "higher":
        lines.append("📈 Вы используете <b>более агрессивные</b> параметры")
        lines.append("   (более высокая производительность)")
    else:  # manual
        lines.append("✏️ Вы <b>вручную подобрали</b> параметры")
        lines.append("   (учитывая конкретные условия и опыт)")

    lines.append("")
    lines.append("<i>Это решение будет сохранено для обучения ИИ-технолога.</i>")
    lines.append("<i>Спасибо за ваш опыт! 🧠</i>")

    return "\n".join(lines)


# ============================================================================
# ОСНОВНЫЕ ДИАЛОГОВЫЕ ФУНКЦИИ
# ============================================================================

async def start_dialog(message: types.Message, state: FSMContext):
    """Начать новый диалог по подбору режимов."""
    await state.clear()

    # Начинаем сбор данных
    await state.set_state("waiting_material")

    await message.answer(
        "🎯 <b>ПОДБОР РЕЖИМОВ РЕЗАНИЯ</b>\n\n"
        "Сейчас мы подберём параметры обработки и сравним с вашей практикой.\n\n"
        "🧠 <i>Цель: собрать РЕАЛЬНЫЕ данные о том, как работают практики.</i>\n\n"
        "Выберите материал заготовки:",
        reply_markup=create_material_keyboard()
    )


async def ask_experience_level(message: types.Message, state: FSMContext):
    """Спросить уровень опыта (опционально)."""
    await message.answer(
        "👤 <b>Уровень опыта (опционально)</b>\n\n"
        "Выберите ваш уровень опыта работы на станках:\n"
        "<i>Эта информация поможет лучше понимать ваши решения.</i>",
        reply_markup=create_experience_level_keyboard()
    )


async def ask_machine_details(message: types.Message, state: FSMContext):
    """Спросить детали станка."""
    await state.set_state("waiting_machine_type")

    await message.answer(
        "🏭 <b>Информация о станке</b>\n\n"
        "Выберите тип вашего станка:",
        reply_markup=create_machine_type_keyboard()
    )


async def ask_tool_details(message: types.Message, state: FSMContext):
    """Спросить детали инструмента."""
    await state.set_state("waiting_tool_material")

    await message.answer(
        "🔧 <b>Информация об инструменте</b>\n\n"
        "Из какого материала пластина/резец?",
        reply_markup=create_tool_material_keyboard()
    )


async def ask_geometry(message: types.Message, state: FSMContext):
    """Спросить геометрические параметры."""
    await state.set_state("waiting_diameter_start")

    await message.answer(
        "📏 <b>Геометрические параметры</b>\n\n"
        "Введите начальный диаметр заготовки в мм:\n"
        "<i>(например: 100, 50.5, 200)</i>",
        reply_markup=types.ReplyKeyboardRemove()
    )


async def calculate_and_show_recommendation(
        message: types.Message,
        state: FSMContext,
        context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Рассчитать рекомендацию и показать её пользователю.

    Returns:
        Словарь с рекомендацией или None при ошибке
    """
    try:
        # Создаем калькулятор из контекста
        calculator = create_calculator_from_context(context)

        # Получаем рекомендацию
        operation_type = context.get('operation', 'roughing')
        if 'чернов' in str(operation_type).lower():
            op_type = 'roughing'
        elif 'чист' in str(operation_type).lower():
            op_type = 'finishing'
        else:
            op_type = 'semi_finishing'

        recommendation = calculator.get_recommendation(op_type)

        # Сохраняем рекомендацию в состояние
        await state.update_data(
            recommendation=recommendation,
            calculator_context=context
        )

        # Показываем пользователю
        await message.answer(
            format_recommendation_message(recommendation, context),
            parse_mode="HTML"
        )

        # Спрашиваем про обороты (первый параметр для сравнения)
        await ask_comparison(message, state, "rpm", recommendation)

        return recommendation

    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка расчета:</b>\n\n"
            f"{str(e)}\n\n"
            f"Пожалуйста, проверьте введенные данные и попробуйте снова.",
            reply_markup=create_main_menu_keyboard()
        )
        await state.clear()
        return None


async def ask_comparison(
        message: types.Message,
        state: FSMContext,
        parameter: str,
        recommendation: Dict[str, Any]
):
    """
    Спросить пользователя: "А как вы делаете на практике?"

    Args:
        parameter: "rpm", "feed", или "ap"
    """
    await state.set_state(f"waiting_comparison_{parameter}")

    await message.answer(
        format_comparison_question(recommendation, parameter),
        parse_mode="HTML",
        reply_markup=create_comparison_keyboard()
    )


async def handle_comparison_choice(
        callback_query: types.CallbackQuery,
        state: FSMContext,
        choice: str,
        parameter: str
):
    """
    Обработать выбор пользователя в сравнении.

    Args:
        choice: "lower", "same", "higher", "manual"
    """
    data = await state.get_data()
    recommendation = data.get('recommendation', {})

    # Сохраняем выбор для текущего параметра
    current_choices = data.get('comparison_choices', {})
    current_choices[parameter] = choice
    await state.update_data(comparison_choices=current_choices)

    # Рассчитываем значение пользователя на основе выбора
    recommended_value = recommendation.get(parameter, 0)
    user_value = None

    if choice == "lower":
        user_value = recommended_value * 0.8  # на 20% меньше
    elif choice == "same":
        user_value = recommended_value  # такое же
    elif choice == "higher":
        user_value = recommended_value * 1.2  # на 20% больше

    # Сохраняем значение пользователя
    if user_value is not None:
        current_values = data.get('user_values', {})
        current_values[parameter] = user_value
        await state.update_data(user_values=current_values)

        # Переходим к следующему параметру
        await proceed_to_next_parameter(callback_query.message, state, parameter)

    else:  # manual - запрашиваем ручной ввод
        await state.set_state(f"waiting_manual_{parameter}")
        await callback_query.message.answer(
            format_manual_input_prompt(recommendation, parameter),
            parse_mode="HTML",
            reply_markup=create_manual_input_keyboard()
        )

    await callback_query.answer()


async def proceed_to_next_parameter(
        message: types.Message,
        state: FSMContext,
        current_parameter: str
):
    """
    Перейти к следующему параметру для сравнения.
    """
    parameters = ["rpm", "feed", "ap"]

    try:
        current_idx = parameters.index(current_parameter)

        if current_idx < len(parameters) - 1:
            # Переходим к следующему параметру
            next_param = parameters[current_idx + 1]
            data = await state.get_data()
            recommendation = data.get('recommendation', {})

            await ask_comparison(message, state, next_param, recommendation)

        else:
            # Все параметры собраны - показываем сводку
            await show_decision_summary(message, state)

    except ValueError:
        # Неизвестный параметр - завершаем
        await show_decision_summary(message, state)


async def handle_manual_input(
        message: types.Message,
        state: FSMContext,
        parameter: str,
        value_text: str
):
    """Обработать ручной ввод параметра."""
    try:
        # Парсим значение
        value = float(value_text.replace(',', '.'))

        # Проверяем разумность значения
        data = await state.get_data()
        recommendation = data.get('recommendation', {})
        recommended = recommendation.get(parameter, 0)

        if recommended > 0:
            ratio = value / recommended

            # Предупреждение при экстремальных значениях
            if ratio < 0.1 or ratio > 10:
                await message.answer(
                    f"⚠️ <b>Внимание:</b> ваше значение отличается от рекомендации в {ratio:.1f} раз\n"
                    f"Это нормально? (Если да, продолжайте)",
                    reply_markup=create_manual_input_keyboard()
                )
                return

        # Сохраняем значение
        current_values = data.get('user_values', {})
        current_values[parameter] = value

        current_choices = data.get('comparison_choices', {})
        current_choices[parameter] = "manual"

        await state.update_data(
            user_values=current_values,
            comparison_choices=current_choices
        )

        # Удаляем клавиатуру ручного ввода
        await message.answer(
            f"✅ Сохранено: {value}",
            reply_markup=types.ReplyKeyboardRemove()
        )

        # Переходим к следующему параметру
        await proceed_to_next_parameter(message, state, parameter)

    except ValueError:
        await message.answer(
            "❌ <b>Ошибка:</b> введите число (например: 1000, 1500.5)\n"
            "Попробуйте снова:",
            reply_markup=create_manual_input_keyboard()
        )


async def show_decision_summary(message: types.Message, state: FSMContext):
    """Показать сводку решения и запросить подтверждение."""
    data = await state.get_data()

    recommendation = data.get('recommendation', {})
    user_values = data.get('user_values', {})
    comparison_choices = data.get('comparison_choices', {})

    # Определяем общую категорию сравнения
    if not comparison_choices:
        comparison = "manual"
    else:
        # Самый частый выбор
        from collections import Counter
        counter = Counter(comparison_choices.values())
        comparison = counter.most_common(1)[0][0]

    await message.answer(
        format_decision_summary(recommendation, user_values, comparison),
        parse_mode="HTML",
        reply_markup=create_confirmation_keyboard()
    )

    await state.set_state("waiting_confirmation")


async def save_user_decision(
        message: types.Message,
        state: FSMContext,
        user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Сохранить решение пользователя в БД.

    Returns:
        Данные сохраненного решения или None при ошибке
    """
    try:
        data = await state.get_data()

        # Собираем все данные
        context = data.get('calculator_context', {})
        recommendation = data.get('recommendation', {})
        user_values = data.get('user_values', {})
        comparison_choices = data.get('comparison_choices', {})

        # Определяем общий выбор сравнения
        if comparison_choices:
            from collections import Counter
            counter = Counter(comparison_choices.values())
            overall_choice = counter.most_common(1)[0][0]
        else:
            overall_choice = "manual"

        # Создаем запись для сохранения
        decision_data = {
            'user_id': user_id,
            'geometry': {
                'diameter_start_mm': context.get('diameter_start', 0),
                'diameter_end_mm': context.get('diameter_end', 0),
                'length_mm': context.get('length', 50.0),
            },
            'operation': {
                'operation_type': context.get('operation', 'roughing'),
                'is_external': context.get('is_external', True),
            },
            'bot_recommendation': {
                'vc': recommendation.get('vc', 0),
                'rpm': recommendation.get('rpm', 0),
                'feed': recommendation.get('feed', 0),
                'ap': recommendation.get('ap', 0),
                'power_kw': recommendation.get('power_kw', 0),
                'passes_strategy': recommendation.get('passes_strategy', {}),
                'total_passes': recommendation.get('total_passes', 1),
            },
            'user_actual': {
                'rpm': user_values.get('rpm', 0),
                'feed': user_values.get('feed', 0),
                'ap': user_values.get('ap', 0),
                'comparison_choice': overall_choice,
            },
            'source': 'telegram',
            'session_id': str(state.key),
            'full_context': {
                'context': context,
                'recommendation': recommendation,
                'user_values': user_values,
                'comparison_choices': comparison_choices,
            }
        }

        # TODO: Реальная сохранение в БД через storage.models.save_user_decision
        # Пока просто возвращаем данные
        return decision_data

    except Exception as e:
        print(f"Ошибка сохранения решения: {e}")
        return None


# ============================================================================
# УТИЛИТЫ ДЛЯ ОБРАБОТКИ ВВОДА
# ============================================================================

def parse_diameter_input(text: str) -> Optional[float]:
    """Парсить ввод диаметра."""
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
            value = float(match.group())

            # Проверка разумности
            if 0.1 <= value <= 1000:
                return value

        return None
    except:
        return None


def parse_power_input(text: str) -> Optional[float]:
    """Парсить ввод мощности."""
    try:
        # Ищем число в тексте
        import re
        match = re.search(r'\d+(?:[.,]\d+)?', text)
        if match:
            value = float(match.group().replace(',', '.'))

            # Проверка разумности
            if 1 <= value <= 200:
                return value

        return None
    except:
        return None


# ============================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ (для интеграции в telegram_bot.py)
# ============================================================================

"""
Пример интеграции в существующий бот:

1. Замените старые диалоги на новые:

# Вместо старой логики:
@dp.message(F.text == "🎯 Подбор режимов")
async def start_mode_selection(message: Message, state: FSMContext):
    await start_dialog(message, state)

# Обработка выбора материала:
@dp.message(F.state == "waiting_material")
async def handle_material(message: Message, state: FSMContext):
    material = message.text
    if material == "🔙 Назад":
        await message.answer("Возврат в меню", reply_markup=create_main_menu_keyboard())
        await state.clear()
        return

    await state.update_data(material=material)
    await ask_machine_details(message, state)

2. Добавьте обработчики для кнопок сравнения:

@dp.callback_query(F.data.startswith("comparison_"))
async def handle_comparison(callback: CallbackQuery, state: FSMContext):
    # Извлекаем параметр из состояния
    current_state = await state.get_state()
    if current_state and current_state.startswith("waiting_comparison_"):
        parameter = current_state.replace("waiting_comparison_", "")
        choice = callback.data.replace("comparison_", "")

        await handle_comparison_choice(callback, state, choice, parameter)

3. Добавьте обработчик сохранения:

@dp.callback_query(F.data == "save_decision")
async def handle_save_decision(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    decision_data = await save_user_decision(callback.message, state, user_id)

    if decision_data:
        await callback.message.answer(
            "✅ <b>Решение сохранено!</b>\n\n"
            "Спасибо за ваш опыт! Это поможет обучать ИИ-технолога.",
            reply_markup=create_main_menu_keyboard()
        )
    else:
        await callback.message.answer(
            "❌ <b>Ошибка сохранения</b>\n\n"
            "Попробуйте снова.",
            reply_markup=create_main_menu_keyboard()
        )

    await state.clear()
"""