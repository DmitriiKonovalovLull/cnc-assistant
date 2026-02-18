# -*- coding: utf-8 -*-
"""
Локализация: русский, английский, китайский.
Поддержка вложенных ключей, плюрализации, кэширования и валидации.
Использование: t('rec.cutting_speed', lang='ru', vc=100) или t_plural('parts.count', count=5, lang='ru').
"""

import logging
import html
import json
from typing import Dict, Any, Optional, Union, List
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = ('ru', 'en', 'zh')
DEFAULT_LANG = 'ru'
RTL_LANGS = set()  # Для будущего расширения

# Вложенная структура переводов
TRANSLATIONS: Dict[str, Dict[str, Any]] = {
    'ru': {
        'rec': {
            'title': '🎯 <b>РЕКОМЕНДУЮ:</b>',
            'cutting_speed': '⚡ Скорость резания: <code>{vc:.0f} м/мин</code>',
            'rpm': '🔄 Обороты: <code>{rpm:.0f} об/мин</code>',
            'feed': '📏 Подача: <code>{feed:.2f} мм/об</code>',
            'depth': '🔪 Глубина: <code>{ap:.1f} мм</code>',
            'power': '⚙️ Мощность: <code>{power:.1f} кВт</code>',
            'machinability': '⚙️ <b>Обрабатываемость (Machinability):</b> {machinability:.0f}%',
            'mach_very_easy': '   ✅ Очень легко обрабатывается',
            'mach_good': '   ✅ Хорошо обрабатывается',
            'mach_medium': '   ⚠️ Средняя обрабатываемость',
            'mach_hard': '   ⚠️ Трудно обрабатывается - снижены скорости и подачи',
            'rigidity': '🔧 <b>Жесткость инструмента:</b> L/D = {ld_ratio:.1f}',
            'modes_adjusted': '   📉 Режимы скорректированы: Vc×{k_v:.2f}, подача×{k_f:.2f}, глубина×{k_ap:.2f}',
            'internet_used': '🌐 <b>Использованы актуальные данные из интернета</b>',
            'sources': '   📚 Источники: {sources}',
            'why': '<b>Почему такие параметры:</b>',
            'attention': '⚠️ <b>Обратите внимание:</b>',
            'antichatter': '🛡️ <b>Стратегия борьбы с вибрацией:</b>',
            'assumed': '💡 <b>Я предположил:</b>',
            'ask_practice': '💬 <b>Какие параметры вы используете на практике?</b>',
            'ask_practice_hint': '<i>Напишите обороты, подачу, глубину и скорость резания — это улучшит рекомендации.</i>',
            'ask_vibration_photo': '<i>Либо отправьте фото спектра вибрации (кнопка «Анализ вибрации») для подбора безопасных оборотов.</i>',
        },
        'risk': {
            'low': '✅ Жёсткая система',
            'moderate': '⚠️ Умеренный риск вибрации',
            'high': '⚠️ Высокий риск вибрации',
            'critical': '❌ КРИТИЧЕСКИЙ РИСК ВИБРАЦИИ',
        },
        'mat': {
            'steel': 'Для стали использую средние скорости резания',
            'aluminum': 'Алюминий обрабатывается на высоких скоростях',
            'stainless': 'Нержавейка требует более низких скоростей',
            'titanium': 'Титан обрабатывается очень аккуратно, низкие скорости',
            'default': 'Стандартные параметры для этого материала',
        },
        'mode': {
            'rough': 'Черновая обработка — максимальный съём металла',
            'finish': 'Чистовая обработка — акцент на качество поверхности',
            'semi': 'Получистовая — баланс между производительностью и качеством',
        },
        'msg': {
            'not_understood': '🤔 <b>Не совсем понял ваш запрос.</b>',
            'not_understood_options': '💬 <i>Вы можете:</i>\n• Описать задачу обработки\n• Указать ГОСТ/ОСТ для стандартной детали\n• Написать "что ты можешь" для описания возможностей\n• Написать "помощь" для инструкции\n\n<i>Просто опишите что нужно, я пойму.</i>',
            'not_understood_fallback': '💬 <b>Я могу помочь с:</b>\n\n1️⃣ <b>Рассчитать режимы резания</b>\n   (опиши задачу: материал, диаметры, тип обработки)\n\n2️⃣ <b>Сделать деталь по ГОСТ/ОСТ</b>\n   (напиши номер стандарта)\n\n3️⃣ <b>Помочь с технологией</b>\n   (задай вопрос или опиши проблему)\n\n💡 <i>Или просто опиши что нужно сделать, я пойму.</i>',
            'thanks_saved': '✅ <b>Спасибо! Ваш опыт сохранён.</b>\n\n📊 <i>Эти данные помогут улучшить рекомендации для других операторов.</i>\n\n📈 <i>Можете отправить фото спектра вибрации (кнопка «Анализ вибрации») для подбора безопасных оборотов.</i>\n\n💬 <i>Или опишите ещё одну задачу.</i>',
            'describe_params': '💬 <b>Опишите свои параметры резания:</b>\n\nНапример: <code>"обороты 2000, скорость 120 м/мин, подача 0.2, глубина 2 мм"</code>\n\nИли: <code>"даю сьем 2 мм, обороты 2000, скорость резания 120"</code>\n\n📈 <i>Либо отправьте фото спектра вибрации (кнопка «Анализ вибрации») для анализа.</i>',
            'save_failed': '❌ <b>Не удалось сохранить опыт</b>\n\nПопробуйте описать параметры по-другому.',
            'calculation_error': '❌ <b>Ошибка расчета:</b> {error}\n\n💡 <i>Попробуйте описать задачу по-другому.</i>',
            'fsm_disabled': 'FSM отключен, режим свободного диалога',
            'context_reset': '🔄 <b>Контекст сброшен</b>\n\nМожете начать новую задачу.',
            'no_active_context': '📭 <b>Нет активного контекста</b>\n\nНачните с описания задачи.',
            'context_empty': '📭 <b>Контекст пуст</b>\n\nОпишите задачу для начала работы.',
            'history_empty': '📭 История пуста',
            'dialog_history_title': '📋 <b>История диалога:</b>',
            'you': 'Вы',
            'bot': 'Бот',
            'calculation_done': 'Расчет выполнен',
            'recommendation_shown': 'Показана рекомендация',
        },
        'btn': {
            'continue': '▶️ Продолжить',
            'help': '📖 Помощь',
            'new_task': '🔄 Новая задача',
            'history': '📊 История',
            'my_works': '📋 Мои работы',
            'my_tools': '🔧 Мои инструменты',
            'vibration_analysis': '📈 Анализ вибрации',
            'save_work': '💾 Сохранить работу',
            'select_material': '📋 Выбрать материал',
            'input_diameters': '📏 Указать диаметры',
            'select_mode': '⚙️ Выбрать режим',
            'select_machine': '🏭 Выбрать станок',
            'input_text': '✏️ Ввести всё текстом',
            'select_tool': '🔧 Указать инструмент',
        },
        'help': {
            'title': '📖 <b>Помощь по использованию бота</b>',
            'main': '🎯 <b>Основная функция:</b> подбор режимов резания для токарной и фрезерной обработки.',
            'how': '📝 <b>Как описать задачу:</b> материал, диаметры (с Ø100 до Ø90), тип обработки (черновая/чистовая), станок, инструмент — в любом порядке.',
            'examples': '💡 <b>Примеры:</b>\n<code>Титан, токарный ЧПУ, снять с Ø200 до Ø50</code>\n<code>Сталь 45, черновая, Ø100→90</code>',
            'commands': '🔧 <b>Команды:</b> <code>история</code>, <code>мои работы</code>, <code>мои инструменты</code>, <code>сохранить работу</code>, <code>работа W001</code>, <code>помощь</code>.',
            'just_describe': '💬 <i>Просто опиши задачу — я пойму.</i>',
        },
        'lang': {
            'choose': '🌐 Выберите язык / Choose language / 选择语言',
            'ru': 'Русский',
            'en': 'English',
            'zh': '中文',
            'saved': '✅ Язык изменён на: {name}',
        },
        'ctx': {
            'empty': 'Пока нет данных...',
            'material': 'Материал',
            'diameters': 'Диаметры',
            'mode': 'Режим',
            'machine': 'Станок',
        },
        'parts': {
            'count': {
                'one': '{count} деталь',
                'few': '{count} детали',
                'many': '{count} деталей',
            },
        },
    },
    'en': {
        'rec': {
            'title': '🎯 <b>RECOMMEND:</b>',
            'cutting_speed': '⚡ Cutting speed: <code>{vc:.0f} m/min</code>',
            'rpm': '🔄 RPM: <code>{rpm:.0f} rev/min</code>',
            'feed': '📏 Feed: <code>{feed:.2f} mm/rev</code>',
            'depth': '🔪 Depth: <code>{ap:.1f} mm</code>',
            'power': '⚙️ Power: <code>{power:.1f} kW</code>',
            'machinability': '⚙️ <b>Machinability:</b> {machinability:.0f}%',
            'mach_very_easy': '   ✅ Very easy to machine',
            'mach_good': '   ✅ Good machinability',
            'mach_medium': '   ⚠️ Medium machinability',
            'mach_hard': '   ⚠️ Hard to machine — reduced speeds and feeds',
            'rigidity': '🔧 <b>Tool rigidity:</b> L/D = {ld_ratio:.1f}',
            'modes_adjusted': '   📉 Modes adjusted: Vc×{k_v:.2f}, feed×{k_f:.2f}, depth×{k_ap:.2f}',
            'internet_used': '🌐 <b>Live data from the internet used</b>',
            'sources': '   📚 Sources: {sources}',
            'why': '<b>Why these parameters:</b>',
            'attention': '⚠️ <b>Note:</b>',
            'antichatter': '🛡️ <b>Anti-chatter strategy:</b>',
            'assumed': '💡 <b>I assumed:</b>',
            'ask_practice': '💬 <b>What parameters do you use in practice?</b>',
            'ask_practice_hint': '<i>Reply with RPM, feed, depth and cutting speed — this improves recommendations.</i>',
            'ask_vibration_photo': '<i>Or send a vibration spectrum photo (button «Vibration analysis») for safe RPM.</i>',
        },
        'risk': {
            'low': '✅ Rigid setup',
            'moderate': '⚠️ Moderate vibration risk',
            'high': '⚠️ High vibration risk',
            'critical': '❌ CRITICAL VIBRATION RISK',
        },
        'mat': {
            'steel': 'Standard cutting speeds for steel',
            'aluminum': 'Aluminum — high cutting speeds',
            'stainless': 'Stainless — lower speeds',
            'titanium': 'Titanium — careful, low speeds',
            'default': 'Standard parameters for this material',
        },
        'mode': {
            'rough': 'Roughing — maximum metal removal',
            'finish': 'Finishing — focus on surface quality',
            'semi': 'Semi-finishing — balance of productivity and quality',
        },
        'msg': {
            'not_understood': '🤔 <b>I didn\'t quite get that.</b>',
            'not_understood_options': '💬 <i>You can:</i>\n• Describe the machining task\n• Give a standard part (e.g. GOST/ISO)\n• Type "what can you do" for capabilities\n• Type "help" for instructions\n\n<i>Just describe what you need.</i>',
            'not_understood_fallback': '💬 <b>I can help with:</b>\n\n1️⃣ <b>Cutting parameters</b>\n   (describe: material, diameters, operation type)\n\n2️⃣ <b>Standard parts (GOST/ISO)</b>\n   (give standard number)\n\n3️⃣ <b>Process advice</b>\n   (ask a question or describe a problem)\n\n💡 <i>Or just describe what you need.</i>',
            'thanks_saved': '✅ <b>Thanks! Your experience has been saved.</b>\n\n📊 <i>This helps improve recommendations for others.</i>\n\n📈 <i>You can send a vibration spectrum photo (button «Vibration analysis») for safe RPM.</i>\n\n💬 <i>Or describe another task.</i>',
            'describe_params': '💬 <b>Describe your cutting parameters:</b>\n\nE.g.: <code>"2000 rpm, 120 m/min, feed 0.2, depth 2 mm"</code>\n\n📈 <i>Or send a vibration spectrum photo (button «Vibration analysis»).</i>',
            'save_failed': '❌ <b>Could not save experience.</b>\n\nTry describing parameters differently.',
            'calculation_error': '❌ <b>Calculation error:</b> {error}\n\n💡 <i>Try describing the task differently.</i>',
            'fsm_disabled': 'FSM disabled, free dialogue mode',
            'context_reset': '🔄 <b>Context reset</b>\n\nYou can start a new task.',
            'no_active_context': '📭 <b>No active context</b>\n\nStart by describing a task.',
            'context_empty': '📭 <b>Context is empty</b>\n\nDescribe a task to start working.',
            'history_empty': '📭 History is empty',
            'dialog_history_title': '📋 <b>Dialog history:</b>',
            'you': 'You',
            'bot': 'Bot',
            'calculation_done': 'Calculation completed',
            'recommendation_shown': 'Recommendation shown',
        },
        'btn': {
            'continue': '▶️ Continue',
            'help': '📖 Help',
            'new_task': '🔄 New task',
            'history': '📊 History',
            'my_works': '📋 My works',
            'my_tools': '🔧 My tools',
            'vibration_analysis': '📈 Vibration analysis',
            'save_work': '💾 Save work',
            'select_material': '📋 Select material',
            'input_diameters': '📏 Enter diameters',
            'select_mode': '⚙️ Select mode',
            'select_machine': '🏭 Select machine',
            'input_text': '✏️ Enter as text',
            'select_tool': '🔧 Specify tool',
        },
        'help': {
            'title': '📖 <b>Help</b>',
            'main': '🎯 <b>Main function:</b> cutting parameter selection for turning and milling.',
            'how': '📝 <b>How to describe:</b> material, diameters (e.g. Ø100 to Ø90), operation (rough/finish), machine, tool — any order.',
            'examples': '💡 <b>Examples:</b>\n<code>Titanium, CNC lathe, Ø200 to Ø50</code>\n<code>Steel 45, rough, Ø100→90</code>',
            'commands': '🔧 <b>Commands:</b> <code>history</code>, <code>my works</code>, <code>my tools</code>, <code>save work</code>, <code>work W001</code>, <code>help</code>.',
            'just_describe': '💬 <i>Just describe the task.</i>',
        },
        'lang': {
            'choose': '🌐 Choose language',
            'ru': 'Русский',
            'en': 'English',
            'zh': '中文',
            'saved': '✅ Language set to: {name}',
        },
        'ctx': {
            'empty': 'No data yet...',
            'material': 'Material',
            'diameters': 'Diameters',
            'mode': 'Mode',
            'machine': 'Machine',
        },
        'parts': {
            'count': {
                'one': '{count} part',
                'few': '{count} parts',
                'many': '{count} parts',
            },
        },
    },
    'zh': {
        'rec': {
            'title': '🎯 <b>推荐：</b>',
            'cutting_speed': '⚡ 切削速度：<code>{vc:.0f} 米/分</code>',
            'rpm': '🔄 转速：<code>{rpm:.0f} 转/分</code>',
            'feed': '📏 进给：<code>{feed:.2f} 毫米/转</code>',
            'depth': '🔪 切深：<code>{ap:.1f} 毫米</code>',
            'power': '⚙️ 功率：<code>{power:.1f} 千瓦</code>',
            'machinability': '⚙️ <b>可加工性：</b>{machinability:.0f}%',
            'mach_very_easy': '   ✅ 极易加工',
            'mach_good': '   ✅ 可加工性好',
            'mach_medium': '   ⚠️ 中等可加工性',
            'mach_hard': '   ⚠️ 难加工 — 已降低转速和进给',
            'rigidity': '🔧 <b>刀具刚性：</b>L/D = {ld_ratio:.1f}',
            'modes_adjusted': '   📉 已修正：Vc×{k_v:.2f}，进给×{k_f:.2f}，切深×{k_ap:.2f}',
            'internet_used': '🌐 <b>已使用网络实时数据</b>',
            'sources': '   📚 来源：{sources}',
            'why': '<b>参数说明：</b>',
            'attention': '⚠️ <b>注意：</b>',
            'antichatter': '🛡️ <b>减振策略：</b>',
            'assumed': '💡 <b>我假设：</b>',
            'ask_practice': '💬 <b>您实际使用的参数？</b>',
            'ask_practice_hint': '<i>请回复转速、进给、切深和切削速度 — 用于改进推荐。</i>',
            'ask_vibration_photo': '<i>或发送振动频谱照片（「振动分析」按钮）以推荐安全转速。</i>',
        },
        'risk': {
            'low': '✅ 刚性良好',
            'moderate': '⚠️ 振动风险中等',
            'high': '⚠️ 振动风险高',
            'critical': '❌ 振动风险严重',
        },
        'mat': {
            'steel': '钢材采用中等切削速度',
            'aluminum': '铝合金 — 高切削速度',
            'stainless': '不锈钢 — 较低速度',
            'titanium': '钛合金 — 需谨慎，低速度',
            'default': '该材料的标准参数',
        },
        'mode': {
            'rough': '粗加工 — 最大金属去除量',
            'finish': '精加工 — 保证表面质量',
            'semi': '半精加工 — 效率与质量平衡',
        },
        'msg': {
            'not_understood': '🤔 <b>没太理解您的意思。</b>',
            'not_understood_options': '💬 <i>您可以：</i>\n• 描述加工任务\n• 给出标准件号（如国标/ISO）\n• 输入「你能做什么」查看功能\n• 输入「帮助」查看说明\n\n<i>直接描述您的需求即可。</i>',
            'not_understood_fallback': '💬 <b>我可以帮您：</b>\n\n1️⃣ <b>切削参数</b>\n   （描述：材料、直径、加工类型）\n\n2️⃣ <b>标准件（国标/ISO）</b>\n   （给出标准号）\n\n3️⃣ <b>工艺建议</b>\n   （提问或描述问题）\n\n💡 <i>或直接描述需求。</i>',
            'thanks_saved': '✅ <b>谢谢！您的经验已保存。</b>\n\n📊 <i>将用于改进对他人的推荐。</i>\n\n📈 <i>可发送振动频谱照片（「振动分析」按钮）以推荐安全转速。</i>\n\n💬 <i>或描述下一个任务。</i>',
            'describe_params': '💬 <b>请描述您的切削参数：</b>\n\n例如：<code>转速2000、120米/分、进给0.2、切深2毫米</code>\n\n📈 <i>或发送振动频谱照片（「振动分析」按钮）。</i>',
            'save_failed': '❌ <b>保存失败。</b>\n\n请换一种方式描述参数。',
            'calculation_error': '❌ <b>计算错误：</b>{error}\n\n💡 <i>请换一种方式描述任务。</i>',
            'fsm_disabled': 'FSM已禁用，自由对话模式',
            'context_reset': '🔄 <b>上下文已重置</b>\n\n您可以开始新任务。',
            'no_active_context': '📭 <b>没有活动上下文</b>\n\n请先描述任务。',
            'context_empty': '📭 <b>上下文为空</b>\n\n请描述任务以开始工作。',
            'history_empty': '📭 历史记录为空',
            'dialog_history_title': '📋 <b>对话历史：</b>',
            'you': '您',
            'bot': '机器人',
            'calculation_done': '计算完成',
            'recommendation_shown': '已显示推荐',
        },
        'btn': {
            'continue': '▶️ 继续',
            'help': '📖 帮助',
            'new_task': '🔄 新任务',
            'history': '📊 历史',
            'my_works': '📋 我的工作',
            'my_tools': '🔧 我的刀具',
            'vibration_analysis': '📈 振动分析',
            'save_work': '💾 保存工作',
            'select_material': '📋 选择材料',
            'input_diameters': '📏 输入直径',
            'select_mode': '⚙️ 选择模式',
            'select_machine': '🏭 选择机床',
            'input_text': '✏️ 文字输入',
            'select_tool': '🔧 指定刀具',
        },
        'help': {
            'title': '📖 <b>使用说明</b>',
            'main': '🎯 <b>主要功能：</b>车削、铣削切削参数推荐。',
            'how': '📝 <b>如何描述：</b>材料、直径（如Ø100到Ø90）、加工类型（粗/精）、机床、刀具 — 顺序任意。',
            'examples': '💡 <b>示例：</b>\n<code>钛合金，数控车床，Ø200到Ø50</code>\n<code>45钢，粗车，Ø100→90</code>',
            'commands': '🔧 <b>命令：</b><code>历史</code>、<code>我的工作</code>、<code>我的刀具</code>、<code>保存工作</code>、<code>工作 W001</code>、<code>帮助</code>。',
            'just_describe': '💬 <i>直接描述任务即可。</i>',
        },
        'lang': {
            'choose': '🌐 选择语言',
            'ru': 'Русский',
            'en': 'English',
            'zh': '中文',
            'saved': '✅ 语言已设为：{name}',
        },
        'ctx': {
            'empty': '暂无数据...',
            'material': '材料',
            'diameters': '直径',
            'mode': '模式',
            'machine': '机床',
        },
        'parts': {
            'count': {
                'one': '{count} 零件',
                'few': '{count} 零件',
                'many': '{count} 零件',
            },
        },
    },
}


def _get_nested_value(data: Dict[str, Any], key_path: str) -> Optional[str]:
    """
    Получить значение из вложенного словаря по точечной нотации.
    
    Args:
        data: Вложенный словарь
        key_path: Путь к ключу (например 'rec.cutting_speed')
        
    Returns:
        Значение или None
    """
    parts = key_path.split('.')
    current = data
    
    try:
        for part in parts:
            if isinstance(current, dict):
                current = current[part]
            else:
                return None
        return current if isinstance(current, str) else None
    except (KeyError, TypeError):
        return None


def _get_all_keys(data: Dict[str, Any], prefix: str = '') -> set:
    """
    Получить все ключи из вложенной структуры в формате точечной нотации.
    
    Args:
        data: Вложенный словарь
        prefix: Префикс для текущего уровня
        
    Returns:
        Множество всех ключей
    """
    keys = set()
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.update(_get_all_keys(value, full_key))
        else:
            keys.add(full_key)
    return keys


def validate_translations() -> Dict[str, List[str]]:
    """
    Проверить, что все ключи присутствуют во всех языках.
    
    Returns:
        Словарь с отсутствующими ключами для каждого языка
    """
    # Получаем все ключи из всех языков
    all_keys = set()
    for lang in SUPPORTED_LANGS:
        if lang in TRANSLATIONS:
            all_keys.update(_get_all_keys(TRANSLATIONS[lang]))
    
    missing = {}
    for lang in SUPPORTED_LANGS:
        if lang not in TRANSLATIONS:
            missing[lang] = list(all_keys)
            continue
        
        lang_keys = _get_all_keys(TRANSLATIONS[lang])
        missing_keys = all_keys - lang_keys
        if missing_keys:
            missing[lang] = sorted(missing_keys)
            logger.warning(f"Missing translations for {lang}: {len(missing_keys)} keys")
    
    return missing


def pluralize_ru(count: Union[int, float]) -> str:
    """
    Выбрать правильную форму для русского языка.
    
    Args:
        count: Количество
        
    Returns:
        'one', 'few' или 'many'
    """
    count_abs = abs(int(count))
    if count_abs % 10 == 1 and count_abs % 100 != 11:
        return 'one'
    elif 2 <= count_abs % 10 <= 4 and (count_abs % 100 < 10 or count_abs % 100 >= 20):
        return 'few'
    else:
        return 'many'


def get_lang(context: Optional[Any] = None, user_id: Optional[str] = None) -> str:
    """
    Получить язык из контекста, user_id или базы данных.
    Приоритет: context.lang > user_preferences > DEFAULT_LANG
    
    Args:
        context: Контекст с атрибутом lang
        user_id: ID пользователя для поиска в БД
        
    Returns:
        Код языка
    """
    # 1. Из контекста
    if context is not None:
        if hasattr(context, 'lang'):
            lang = getattr(context, 'lang', None)
            if lang and lang in SUPPORTED_LANGS:
                return lang
    
    # 2. Из базы данных по user_id (если есть модель UserPreferences)
    if user_id:
        try:
            from app.storage.models import UserPreferences
            # Предполагаем что есть метод get_user_preferences или подобный
            # Это зависит от вашей структуры БД
            # prefs = UserPreferences.get(user_id)
            # if prefs and prefs.lang in SUPPORTED_LANGS:
            #     return prefs.lang
        except (ImportError, Exception):
            pass
    
    # 3. По умолчанию
    return DEFAULT_LANG


def get_text_direction(lang: str) -> str:
    """
    Получить направление текста для языка.
    
    Args:
        lang: Код языка
        
    Returns:
        'ltr' или 'rtl'
    """
    return 'rtl' if lang in RTL_LANGS else 'ltr'


@lru_cache(maxsize=1000)
def _get_template_cached(key: str, lang: str) -> Optional[str]:
    """
    Получить шаблон перевода с кэшированием.
    
    Args:
        key: Ключ перевода
        lang: Язык
        
    Returns:
        Шаблон строки или None
    """
    if lang not in TRANSLATIONS:
        lang = DEFAULT_LANG
    
    template = _get_nested_value(TRANSLATIONS[lang], key)
    if template is None and lang != DEFAULT_LANG:
        template = _get_nested_value(TRANSLATIONS[DEFAULT_LANG], key)
    
    return template


def t(key: str, lang: Optional[str] = None, default: Optional[str] = None, **kwargs: Any) -> str:
    """
    Перевод по ключу с поддержкой точечной нотации.
    
    Args:
        key: Ключ перевода (например 'rec.cutting_speed')
        lang: Язык (если None - используется DEFAULT_LANG)
        default: Значение по умолчанию если ключ не найден
        **kwargs: Параметры для форматирования строки
        
    Returns:
        Переведенная строка
    """
    # Явная проверка языка
    lang = lang if lang and lang in SUPPORTED_LANGS else DEFAULT_LANG
    
    # Получаем шаблон с кэшированием
    template = _get_template_cached(key, lang)
    
    if template is None:
        # Fallback на default или сам ключ
        if default is not None:
            template = default
        else:
            template = key
    
    # Форматируем строку если есть параметры
    if kwargs and isinstance(template, str):
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.debug(f"Format error for key '{key}': {e}")
            return template
    
    return template


def t_plural(
    key: str,
    count: Union[int, float],
    lang: Optional[str] = None,
    default: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    Перевод с учетом множественного числа.
    
    Args:
        key: Базовый ключ перевода (например 'parts.count')
        count: Количество
        lang: Язык
        default: Значение по умолчанию
        **kwargs: Дополнительные параметры для форматирования
        
    Returns:
        Переведенная строка с правильной формой множественного числа
    """
    lang = lang if lang and lang in SUPPORTED_LANGS else DEFAULT_LANG
    
    # Для русского языка используем плюрализацию
    if lang == 'ru':
        form = pluralize_ru(count)
        plural_key = f"{key}.{form}"
        template = _get_template_cached(plural_key, lang)
        
        if template is None:
            # Fallback на другие формы
            for fallback_form in ['one', 'few', 'many']:
                fallback_key = f"{key}.{fallback_form}"
                template = _get_template_cached(fallback_key, lang)
                if template:
                    break
        
        if template:
            kwargs['count'] = count
            try:
                return template.format(**kwargs)
            except (KeyError, ValueError):
                return template
    
    # Для других языков используем обычный перевод
    return t(key, lang=lang, default=default, count=count, **kwargs)


def t_safe(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Перевод с безопасным HTML (только разрешенные теги).
    
    Args:
        key: Ключ перевода
        lang: Язык
        **kwargs: Параметры для форматирования
        
    Returns:
        Безопасная HTML строка
    """
    import re
    result = t(key, lang=lang, **kwargs)
    
    # Разрешаем только <b>, <i>, <code>
    allowed_tags = ['b', 'i', 'code']
    
    # Экранируем все HTML
    escaped = html.escape(result)
    
    # Восстанавливаем разрешенные теги
    for tag in allowed_tags:
        escaped = escaped.replace(f'&lt;{tag}&gt;', f'<{tag}>')
        escaped = escaped.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
    
    return escaped


def t_escaped(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Перевод с полным экранированием HTML.
    
    Args:
        key: Ключ перевода
        lang: Язык
        **kwargs: Параметры для форматирования
        
    Returns:
        Полностью экранированная строка
    """
    result = t(key, lang=lang, **kwargs)
    return html.escape(result)


def format_number(num: float, lang: str, decimals: int = 1) -> str:
    """
    Форматировать число с учетом локали.
    
    Args:
        num: Число
        lang: Язык
        decimals: Количество знаков после запятой
        
    Returns:
        Отформатированное число
    """
    if lang == 'ru':
        return f"{num:.{decimals}f}".replace('.', ',')
    return f"{num:.{decimals}f}"


def t_formatted(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Перевод с форматированием чисел по локали.
    
    Args:
        key: Ключ перевода
        lang: Язык
        **kwargs: Параметры (числовые значения будут отформатированы)
        
    Returns:
        Переведенная строка с отформатированными числами
    """
    lang = lang if lang and lang in SUPPORTED_LANGS else DEFAULT_LANG
    
    # Форматируем числовые значения
    formatted_kwargs = {}
    for k, v in kwargs.items():
        if isinstance(v, (int, float)):
            # Для ключей, оканчивающихся на _num, применяем локализацию
            if k.endswith('_num'):
                formatted_kwargs[k] = format_number(v, lang)
            else:
                formatted_kwargs[k] = v
        else:
            formatted_kwargs[k] = v
    
    return t(key, lang=lang, **formatted_kwargs)


# Валидация при импорте модуля
_missing_translations = validate_translations()
if _missing_translations:
    logger.warning(f"Translation validation found missing keys: {_missing_translations}")
