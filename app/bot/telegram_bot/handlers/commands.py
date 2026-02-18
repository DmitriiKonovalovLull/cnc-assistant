"""
Обработчики команд бота (/start, /help, /reset, /status, /history, /stats).
"""

import os
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram import types

from app.bot.i18n import t, get_lang
from app.bot.telegram_bot.utils import get_user_context
from app.bot.telegram_bot.formatters import format_context_summary
from app.bot.telegram_bot.keyboards import create_main_nav_keyboard
from app.bot.context_manager import split_long_message, format_for_device, metrics
from app.bot.telegram_bot.main import (
    context_manager, file_storage, user_contexts
)


def register_commands(dp: Dispatcher):
    """Зарегистрировать все команды."""
    dp.message.register(cmd_reset, Command("reset"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_history, Command("history"))
    dp.message.register(cmd_stats, Command("stats"))
    dp.message.register(cmd_start, Command("start", "help"))
    dp.message.register(cmd_lang, Command("lang"))


async def cmd_reset(message: types.Message, state: FSMContext):
    """Сбросить контекст пользователя."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    
    # Удаляем контекст из всех хранилищ
    if context_manager:
        context_manager.delete(user_id)
    if file_storage:
        file_storage.delete(user_id)
    if user_id in user_contexts:
        del user_contexts[user_id]
    
    await state.clear()
    
    await message.answer(
        t('msg.context_reset', lang=lang, default="🔄 <b>Контекст сброшен</b>\n\nМожете начать новую задачу.")
    )


async def cmd_status(message: types.Message, state: FSMContext):
    """Показать текущее состояние контекста."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    
    # Используем единую функцию получения контекста
    context = await get_user_context(user_id)
    
    if not context:
        await message.answer(
            t('msg.no_active_context', lang=lang, default="📭 <b>Нет активного контекста</b>\n\nНачните с описания задачи.")
        )
        return
    
    summary = format_context_summary(context)
    if summary == "Пока нет данных...":
        await message.answer(
            t('msg.context_empty', lang=lang, default="📭 <b>Контекст пуст</b>\n\nОпишите задачу для начала работы.")
        )
    else:
        summary = format_for_device(summary, False)
        summary_parts = split_long_message(summary)
        for part in summary_parts:
            await message.answer(part)


async def cmd_history(message: types.Message, state: FSMContext):
    """Показать историю диалога."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    
    # Используем единую функцию получения контекста
    context = await get_user_context(user_id)
    
    if not context or not context.dialog_history:
        await message.answer(t('msg.history_empty', lang=lang, default="📭 История пуста"))
        return
    
    lines = [t('msg.dialog_history_title', lang=lang, default="📋 <b>История диалога:</b>") + "\n"]
    
    for i, entry in enumerate(context.dialog_history[-10:], 1):  # Последние 10
        event = entry.get('event', 'unknown')
        data = entry.get('data', {})
        
        if event == 'user_message':
            text = data.get('text', '')[:50]
            lines.append(f"{i}. 👤 <b>{t('msg.you', lang=lang, default='Вы')}:</b> {text}...")
        elif event == 'calculation':
            lines.append(f"{i}. 🤖 <b>{t('msg.bot', lang=lang, default='Бот')}:</b> {t('msg.calculation_done', lang=lang, default='Расчет выполнен')}")
        elif event == 'recommendation_shown':
            lines.append(f"{i}. 🤖 <b>{t('msg.bot', lang=lang, default='Бот')}:</b> {t('msg.recommendation_shown', lang=lang, default='Показана рекомендация')}")
    
    history_text = "\n".join(lines)
    history_parts = split_long_message(history_text)
    for part in history_parts:
        await message.answer(part)


async def cmd_stats(message: types.Message, state: FSMContext):
    """Показать статистику бота (только для админов)."""
    user_id = str(message.from_user.id)
    
    # Проверка на админа
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    if user_id not in admin_ids:
        await message.answer("⛔ Доступ запрещен")
        return
    
    stats = metrics.get_stats()
    
    response = (
        f"📊 <b>Статистика бота:</b>\n\n"
        f"👥 Пользователей: {stats['users_count']}\n"
        f"💬 Сообщений: {stats['total_messages']}\n"
        f"📸 Фото: {stats['total_photos']}\n"
        f"🧮 Расчетов: {stats['total_calculations']}\n"
        f"❌ Ошибок: {stats['total_errors']}\n\n"
        f"⏱️ Среднее время ответа: {stats['avg_response_time']:.2f}с\n"
        f"📈 P95 время ответа: {stats['p95_response_time']:.2f}с"
    )
    
    await message.answer(response)


async def cmd_start(message: types.Message, state: FSMContext):
    """Начало работы с ботом."""
    # Импортируем здесь чтобы избежать циклических зависимостей
    from app.bot.telegram_bot.main import context_repository
    
    await state.clear()
    
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name or "друг"
    
    # Используем единую функцию получения контекста
    context = await get_user_context(user_id)
    
    has_history = context and (
        context.dialog_history or
        context.material or
        context.machine_type or
        context.tool_name
    )
    
    if has_history:
        # Есть история - показываем приветствие с историей
        welcome_text = (
            f"👋 <b>Привет, {user_name}!</b>\n\n"
            f"📋 <b>Я помню нашу предыдущую работу:</b>\n\n"
        )
        
        if context.machine_type:
            known_types = ['токарный чпу', 'токарный ручной', 'фрезерный чпу', 'фрезерный ручной']
            if context.machine_type.lower() not in known_types:
                welcome_text += f"🏭 <b>Станок:</b> {context.machine_type} <i>(сохранён в базу)</i>\n"
            else:
                welcome_text += f"🏭 <b>Станок:</b> {context.machine_type}\n"
        
        if context.material:
            known_materials = ['сталь', 'алюминий', 'нержавейка', 'титан', 'чугун', 'латунь', 'медь']
            if context.material.lower() not in known_materials:
                welcome_text += f"🔩 <b>Материал:</b> {context.material} <i>(сохранён в базу)</i>\n"
            else:
                welcome_text += f"🔩 <b>Материал:</b> {context.material}\n"
        
        if context.tool_name:
            welcome_text += f"🔧 <b>Инструмент:</b> {context.tool_name}\n"
        if context.diameter_start and context.diameter_end:
            welcome_text += f"📏 <b>Диаметры:</b> Ø{context.diameter_start} → Ø{context.diameter_end} мм\n"
        
        welcome_text += (
            "\n💬 <b>Что хотите сделать?</b>\n\n"
            "• Опишите новую задачу обработки\n"
            "• Добавить/изменить инструмент (или отправьте фото)\n"
            "• Изменить параметры станка\n"
            "• Начать с чистого листа (/start для нового контекста)\n\n"
            "<i>Используйте кнопки ниже или напишите что нужно.</i>"
        )
        
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Новая задача", callback_data="new_task")],
            [
                InlineKeyboardButton(text="📊 История", callback_data="show_history"),
                InlineKeyboardButton(text="📋 Мои работы", callback_data="list_works"),
                InlineKeyboardButton(text="🔧 Мои инструменты", callback_data="list_tools"),
            ],
            [
                InlineKeyboardButton(text="🏭 Станок", callback_data="select_machine"),
                InlineKeyboardButton(text="🔧 Инструмент", callback_data="select_tool"),
            ],
            [InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help")],
        ])
        await message.answer(welcome_text, reply_markup=keyboard)
    else:
        # Новая сессия — приветствие
        welcome_text = (
            f"👋 <b>Привет, {user_name}!</b>\n\n"
            f"Я <b>CNC Assistant</b> — помощник по режимам резания для токарки и фрезеровки.\n\n"
            f"📋 <b>Что умею:</b>\n"
            f"• Подбирать обороты, подачи, глубины резания\n"
            f"• Работать по ГОСТ/ОСТ (болты, гайки и т.п.)\n"
            f"• Распознавать технологический маршрут (расточка, сверление, фрезер)\n"
            f"• Сохранять работы и загружать по номеру\n"
            f"• Искать информацию в интернете, если чего-то не знаю\n\n"
            f"💡 <b>Начните с описания задачи:</b>\n"
            f"<code>сталь Ø100→90 черновая токарный ЧПУ</code>"
        )
        await message.answer(welcome_text, reply_markup=create_main_nav_keyboard())


async def cmd_lang(message: types.Message, state: FSMContext):
    """Смена языка."""
    from app.bot.i18n import SUPPORTED_LANGS
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    lang_names = {'ru': '🇷🇺 Русский', 'en': '🇬🇧 English', 'zh': '🇨🇳 中文'}
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang_names.get(lang, lang), callback_data=f"lang_{lang}")]
        for lang in SUPPORTED_LANGS
    ])
    
    await message.answer(
        "🌐 <b>Выберите язык:</b>",
        reply_markup=keyboard
    )
