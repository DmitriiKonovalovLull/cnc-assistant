"""
Клавиатуры для Telegram бота.
"""

from typing import Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.core.context import Context
from app.bot.i18n import t


def create_continue_keyboard(lang: Optional[str] = None) -> InlineKeyboardMarkup:
    """Создать клавиатуру с кнопкой 'Продолжить'."""
    text = t('btn.continue', lang=lang or 'ru')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="continue_work")]
    ])


def create_material_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с вариантами материалов."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сталь", callback_data="material_сталь"),
            InlineKeyboardButton(text="Алюминий", callback_data="material_алюминий")
        ],
        [
            InlineKeyboardButton(text="Нержавейка", callback_data="material_нержавейка"),
            InlineKeyboardButton(text="Титан", callback_data="material_титан")
        ],
        [
            InlineKeyboardButton(text="Чугун", callback_data="material_чугун"),
            InlineKeyboardButton(text="Латунь", callback_data="material_латунь")
        ],
        [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="material_manual")]
    ])
    return keyboard


def create_operation_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с вариантами операций."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Черновая", callback_data="mode_черновая"),
            InlineKeyboardButton(text="Получистовая", callback_data="mode_получистовая")
        ],
        [
            InlineKeyboardButton(text="Чистовая", callback_data="mode_чистовая"),
            InlineKeyboardButton(text="Тонкая", callback_data="mode_тонкая")
        ],
        [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="mode_manual")]
    ])
    return keyboard


def create_machine_type_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру с вариантами станков."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Токарный ЧПУ", callback_data="machine_токарный ЧПУ"),
            InlineKeyboardButton(text="Токарный ручной", callback_data="machine_токарный ручной")
        ],
        [
            InlineKeyboardButton(text="Фрезерный ЧПУ", callback_data="machine_фрезерный ЧПУ"),
            InlineKeyboardButton(text="Фрезерный ручной", callback_data="machine_фрезерный ручной")
        ],
        [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="machine_manual")]
    ])
    return keyboard


def create_clarify_keyboard(missing_fields: list, context: Optional[Context] = None) -> InlineKeyboardMarkup:
    """Создать клавиатуру для уточнения параметров."""
    buttons = []
    
    if 'material' in missing_fields:
        buttons.append([InlineKeyboardButton(text="📋 Выбрать материал", callback_data="select_material")])
    
    if 'diameter_start' in missing_fields or 'diameter_end' in missing_fields:
        buttons.append([InlineKeyboardButton(text="📏 Указать диаметры", callback_data="input_diameters")])
    
    if 'operation' in missing_fields or 'mode' in missing_fields:
        buttons.append([InlineKeyboardButton(text="⚙️ Выбрать режим", callback_data="select_mode")])
    
    if context and not context.machine_type:
        buttons.append([InlineKeyboardButton(text="🏭 Выбрать станок", callback_data="select_machine")])
    
    buttons.append([InlineKeyboardButton(text="✏️ Ввести всё текстом", callback_data="input_text")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_after_calculation_keyboard(lang: Optional[str] = None) -> InlineKeyboardMarkup:
    """Создать клавиатуру после расчета."""
    lang = lang or 'ru'
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t('btn.save_work', lang=lang), callback_data="save_work"),
            InlineKeyboardButton(text=t('btn.new_task', lang=lang), callback_data="new_task")
        ],
        [
            InlineKeyboardButton(text=t('btn.history', lang=lang), callback_data="show_history"),
            InlineKeyboardButton(text=t('btn.my_works', lang=lang), callback_data="list_works"),
            InlineKeyboardButton(text=t('btn.my_tools', lang=lang), callback_data="list_tools")
        ]
    ])


def create_main_nav_keyboard(include_machine_tool: bool = True, lang: Optional[str] = None) -> InlineKeyboardMarkup:
    """Клавиатура навигации для любых экранов."""
    lang = lang or 'ru'
    buttons = [
        [
            InlineKeyboardButton(text=t('btn.help', lang=lang), callback_data="nav_help"),
            InlineKeyboardButton(text=t('btn.history', lang=lang), callback_data="show_history"),
        ],
        [
            InlineKeyboardButton(text=t('btn.my_works', lang=lang), callback_data="list_works"),
            InlineKeyboardButton(text=t('btn.my_tools', lang=lang), callback_data="list_tools"),
            InlineKeyboardButton(text=t('btn.new_task', lang=lang), callback_data="new_task"),
        ],
    ]
    if include_machine_tool:
        buttons.append([
            InlineKeyboardButton(text=t('btn.select_machine', lang=lang), callback_data="select_machine"),
            InlineKeyboardButton(text=t('btn.select_tool', lang=lang), callback_data="select_tool"),
        ])
    buttons.append([
        InlineKeyboardButton(text="🧮 Калькулятор режимов", callback_data="nav_calculator"),
        InlineKeyboardButton(text=t('btn.vibration_analysis', lang=lang), callback_data="nav_vibration"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_post_machine_keyboard() -> InlineKeyboardMarkup:
    """Кнопки после выбора/сохранения станка."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 Указать инструмент", callback_data="select_tool")],
        [
            InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help"),
            InlineKeyboardButton(text="🔄 Новая задача", callback_data="new_task"),
        ],
    ])
