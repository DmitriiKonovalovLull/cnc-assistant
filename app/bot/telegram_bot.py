"""
AI-подобный Telegram бот без кнопок.
Понимает контекст, ведет естественный диалог, делает предположения.
Собирает реальный опыт операторов для обучения ИИ.
"""

import asyncio
import inspect
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Загрузка .env
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Загружен .env из: {env_path}")
else:
    print(f"❌ Файл .env не найден: {env_path}")
    sys.exit(1)

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Импорты новой архитектуры
from app.core.context import Context, DataSource
from app.core.parser import TextParser
from app.core.image_parser import ImageParser
from app.core.assumptions import AssumptionEngine
from app.core.state_machine import SystemState
from app.services.knowledge_service import KnowledgeService
from app.services.tool_saver import ToolSaver
from app.services.recommendation import get_turning_recommendation
from app.services.simple_calculator import SimpleCalculator, SimpleCalculatorInput
from app.bot.handler import MessageHandler
from app.bot.i18n import t, get_lang, SUPPORTED_LANGS
from app.bot.context_manager import (
    ContextManager, RateLimiter, FileContextStorage,
    split_long_message, format_for_device, is_mobile, metrics
)
from app.bot.dialogs import split_long_message as dialogs_split_long_message
from app.storage.models import init_orm_database, get_session, save_user_decision
from app.storage.migrations import run_all_migrations

# Настройка логирования
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(logs_dir / "telegram_bot.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
    logger.error("❌ Токен не найден! Проверьте .env файл")
    sys.exit(1)

# Опциональная настройка пути к Tesseract OCR
_default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == "nt" else None
if _default_tesseract and not os.path.isfile(_default_tesseract):
    _default_tesseract = None
TESSERACT_CMD = os.getenv("TESSERACT_CMD") or os.getenv("TESSERACT_PATH") or _default_tesseract

# Путь к базе данных (абсолютный путь от корня проекта)
db_path = project_root / "app" / "storage" / "cnc.db"
db_path.parent.mkdir(parents=True, exist_ok=True)  # Создаем директорию если её нет
# Для Windows нужно использовать правильный формат пути
if os.name == 'nt':  # Windows
    DB_URL = f"sqlite:///{str(db_path).replace(chr(92), '/')}"
else:  # Unix/Linux/Mac
    DB_URL = f"sqlite:///{db_path.as_posix()}"

# Инициализация бота
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояние FSM для анализа вибрации по фото
class VibrationStates(StatesGroup):
    waiting_photo = State()


class CalculatorStates(StatesGroup):
    """Состояния для простого калькулятора."""
    waiting_operation = State()  # Ожидание типа обработки
    waiting_material = State()  # Ожидание материала
    waiting_machine = State()  # Ожидание станка
    waiting_diameter = State()  # Ожидание диаметра (опционально)
    waiting_tool_radius = State()  # Ожидание радиуса инструмента (опционально)


# Глобальные сервисы (инициализируются при старте)
knowledge_service: Optional[KnowledgeService] = None
handler: Optional[MessageHandler] = None
image_parser: Optional[ImageParser] = None
context_repository: Optional[Any] = None  # ContextRepository
db_pool: Optional[Any] = None  # DatabasePool

# Хранилище контекстов пользователей (в памяти, для обратной совместимости)
# В будущем будет использоваться только context_repository
user_contexts: Dict[str, Context] = {}

# Менеджер контекстов с ограничениями и очисткой
context_manager: Optional[ContextManager] = None

# Rate limiter для защиты от спама
rate_limiter: Optional[RateLimiter] = None

# Файловое хранилище контекстов (опционально)
file_storage: Optional[FileContextStorage] = None


def ensure_context_user_id(context: Context, user_id: str) -> None:
    """
    Убедиться что user_id установлен в контексте перед сохранением.
    
    Args:
        context: Контекст для проверки
        user_id: ID пользователя для установки
    """
    if not context.user_id and user_id:
        context.user_id = user_id
    if not context.session_id:
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _extract_work_number(text: str) -> Optional[str]:
    """Мягкое распознавание номера работы: W001, работа 1, 1 работа, 1, раб 1, w1."""
    if not text or not text.strip():
        return None
    t = text.strip()
    low = t.lower()
    # Явный W + цифры (W001, w1, W12)
    m = re.search(r'\b(w\d+)\b', low, re.I)
    if m:
        num = m.group(1).upper()
        if num[1:].isdigit():
            return f"W{int(num[1:]):03d}" if len(num) <= 4 else f"W{num[1:]}"
    # "работа 1", "work 1", "работу 1", "работа W001"
    m = re.search(r'(?:работа|work|работ[уа])\s+(?:w)?(\d+)', low, re.I)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    # "1 работа", "1 work", "1 раб"
    m = re.search(r'(\d+)\s*(?:работ[ауи]?|work)', low, re.I)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    # Одиночное число в контексте выбора (короткое сообщение: "1", "2", "01")
    m = re.search(r'^(?:№\s*)?(\d+)\s*$', low)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    # (работа|w|№)? цифры — в любом месте для "загрузить работу 1", "открой 3"
    m = re.search(r'(?:работа|work|w|№)\s*(\d+)', low, re.I)
    if m:
        n = m.group(1)
        return f"W{int(n):03d}" if len(n) <= 3 else f"W{n}"
    return None


def _looks_like_experience_feedback(text: str) -> bool:
    """Проверить, похоже ли сообщение на ответ оператора с режимами (обороты, скорость, глубина, подача)."""
    if not text or not text.strip():
        return False
    t = text.strip().lower()
    # Есть числа и ключевые слова режимов
    has_digit = bool(re.search(r'\d+', t))
    patterns = [
        r'оборот', r'об/мин', r'rpm', r'vc\s*=', r'м/мин', r'скорость\s*(?:резания)?',
        r'подач', r'глубин', r'сьем', r'съём', r'съем', r'глубин', r'ap\s*=', r'feed\s*=',
        r'(\d+)\s*мм', r'около\s*\d+', r'максимум\s*\d+', r'даю\s+', r'ставлю\s+',
        r'работаю\s+на\s+\d+', r'применяю\s+\d+'
    ]
    return has_digit and any(re.search(p, t) for p in patterns)


def _extract_work_rename_params(text: str) -> Optional[tuple[str, str]]:
    """Извлечь (work_number, new_name) из текста: переименовать работу W001 в Втулка М12."""
    if not text or not text.strip():
        return None
    t = text.strip()
    # "переименовать работу W001 в Новое название", "назвать работу W001 Втулка"
    m = re.search(
        r'(?:переименовать|назвать)\s+работ[уа]?\s+(W\d+)\s+(?:в\s+)?(.+)',
        t, re.IGNORECASE | re.DOTALL
    )
    if m:
        num = m.group(1).upper()
        name = m.group(2).strip()
        if name:
            return (num, name)
    # "переименовать W001 в Название"
    m = re.search(r'переименовать\s+(W\d+)\s+(?:в\s+)?(.+)', t, re.IGNORECASE | re.DOTALL)
    if m:
        num = m.group(1).upper()
        name = m.group(2).strip()
        if name:
            return (num, name)
    return None


def _extract_tool_display_name(text: str) -> Optional[str]:
    """Извлечь имя инструмента из текста: назови инструмент Мой черновой."""
    if not text or not text.strip():
        return None
    t = text.strip()
    prefixes = [
        r'назови\s+(?:этот\s+)?инструмент\s+',
        r'имя\s+инструмента\s+',
        r'назови\s+инструмент\s+',
    ]
    for pat in prefixes:
        m = re.search(pat + r'(.+)', t, re.IGNORECASE | re.DOTALL)
        if m:
            name = m.group(1).strip()
            if name and len(name) < 100:
                return name
    return None


def save_context_safe(context: Context, user_id: str) -> None:
    """
    Безопасно сохранить контекст с проверкой user_id.
    
    Args:
        context: Контекст для сохранения
        user_id: ID пользователя
    """
    ensure_context_user_id(context, user_id)
    
    # Используем context_manager если доступен
    if context_manager:
        context_manager.set(user_id, context)
    
    # Используем файловое хранилище если доступно
    if file_storage:
        file_storage.set(user_id, context)
    
    # Используем репозиторий если доступен
    if context_repository:
        context_repository.save_context(context)
    else:
        # Fallback на старый способ (в памяти)
        user_contexts[user_id] = context


# ============================================================================
# ФОРМАТИРОВАНИЕ СООБЩЕНИЙ
# ============================================================================

def _format_tool_display(context: Context) -> Optional[str]:
    """Строка для отображения инструмента: имя или марка."""
    if context.tool_display_name and context.tool_name:
        return f"{context.tool_display_name} ({context.tool_name})"
    return context.tool_name or context.tool_display_name


def format_context_summary(context: Context) -> str:
    """Форматировать краткую сводку контекста."""
    lines = []
    
    if context.material:
        source_icon = "👤" if context.is_field_from_user('material') else "🤖"
        lines.append(f"{source_icon} Материал: <b>{context.material}</b>")
    
    if context.diameter_start and context.diameter_end:
        source_icon = "👤" if context.is_field_from_user('diameter_start') else "🤖"
        lines.append(f"{source_icon} Диаметры: <b>Ø{context.diameter_start} → Ø{context.diameter_end} мм</b>")
    
    if context.operation:
        source_icon = "👤" if context.is_field_from_user('operation') else "🤖"
        lines.append(f"{source_icon} Операция: <b>{context.operation}</b>")
    
    if context.mode:
        source_icon = "👤" if context.is_field_from_user('mode') else "🤖"
        lines.append(f"{source_icon} Режим: <b>{context.mode}</b>")
    
    if context.machine_type:
        source_icon = "👤" if context.is_field_from_user('machine_type') else "🤖"
        lines.append(f"{source_icon} Станок: <b>{context.machine_type}</b>")
    
    tool_str = _format_tool_display(context)
    if tool_str:
        lines.append(f"🔧 Инструмент: <b>{tool_str}</b>")
    
    if context.assumptions_made:
        lines.append(f"\n💡 <i>Я предположил: {', '.join(context.assumptions_made)}</i>")
    
    if context.overall_confidence > 0:
        confidence_pct = int(context.overall_confidence * 100)
        lines.append(f"🎯 <i>Уверенность: {confidence_pct}%</i>")
    
    return "\n".join(lines) if lines else "Пока нет данных..."


def format_recommendation(recommendation: Dict[str, Any], context: Context) -> str:
    """Форматировать рекомендацию в естественном виде (с учётом context.lang)."""
    lang = get_lang(context)
    lines = []
    lines.append(t('rec.title', lang=lang))
    lines.append("")
    vc = recommendation.get('vc_m_min') or recommendation.get('vc', 0)
    rpm = recommendation.get('rpm', 0)
    feed = recommendation.get('feed_mm_rev') or recommendation.get('feed', 0)
    ap = recommendation.get('ap_mm') or recommendation.get('ap', 0)
    power = recommendation.get('power_kw', 0)
    lines.append(t('rec.cutting_speed', lang=lang, vc=vc))
    lines.append(t('rec.rpm', lang=lang, rpm=rpm))
    lines.append(t('rec.feed', lang=lang, feed=feed))
    lines.append(t('rec.depth', lang=lang, ap=ap))
    if power > 0:
        lines.append(t('rec.power', lang=lang, power=power))
    context_data = recommendation.get('context', {})
    machinability = context_data.get('machinability')
    if machinability:
        lines.append("")
        lines.append(t('rec.machinability', lang=lang, machinability=machinability))
        if machinability >= 100:
            lines.append(t('rec.mach_very_easy', lang=lang))
        elif machinability >= 70:
            lines.append(t('rec.mach_good', lang=lang))
        elif machinability >= 50:
            lines.append(t('rec.mach_medium', lang=lang))
        else:
            lines.append(t('rec.mach_hard', lang=lang))
    rigidity_info = context_data.get('rigidity_info', {})
    if rigidity_info:
        ld_ratio = rigidity_info.get('ld_ratio')
        risk_level = rigidity_info.get('risk_level')
        if ld_ratio:
            lines.append("")
            lines.append(t('rec.rigidity', lang=lang, ld_ratio=ld_ratio))
            if risk_level in ('low', 'moderate', 'high', 'critical'):
                lines.append("   " + t('risk.' + risk_level, lang=lang))
            rigidity_coeffs = rigidity_info.get('rigidity_coefficients', {})
            if rigidity_coeffs:
                k_v = rigidity_coeffs.get('k_v', 1.0)
                k_f = rigidity_coeffs.get('k_f', 1.0)
                k_ap = rigidity_coeffs.get('k_ap', 1.0)
                if k_v < 1.0 or k_f < 1.0 or k_ap < 1.0:
                    lines.append(t('rec.modes_adjusted', lang=lang, k_v=k_v, k_f=k_f, k_ap=k_ap))
    
    internet_data_used = context_data.get('internet_data_used', False)
    internet_sources = context_data.get('internet_sources', [])
    if internet_data_used and internet_sources:
        lines.append("")
        lines.append(t('rec.internet_used', lang=lang))
        if internet_sources:
            lines.append(t('rec.sources', lang=lang, sources=', '.join(internet_sources[:3])))
    lines.append("")
    lines.append(t('rec.why', lang=lang))
    if context.material:
        mat_key = {'сталь': 'mat.steel', 'алюминий': 'mat.aluminum', 'нержавейка': 'mat.stainless', 'титан': 'mat.titanium'}.get(context.material.lower())
        explanation = t(mat_key or 'mat.default', lang=lang)
        lines.append(f"• {explanation}")
    if context.mode:
        mode_key = {'черновая': 'mode.rough', 'чистовая': 'mode.finish', 'получистовая': 'mode.semi'}.get((context.mode or '').lower())
        if mode_key:
            lines.append("• " + t(mode_key, lang=lang))
    warnings = recommendation.get('warnings', [])
    if warnings:
        lines.append("")
        lines.append(t('rec.attention', lang=lang))
        for warning in warnings[:5]:
            lines.append(f"• {warning}")
    if rigidity_info:
        risk_level = rigidity_info.get('risk_level')
        if risk_level in ('high', 'critical'):
            lines.append("")
            lines.append(t('rec.antichatter', lang=lang))
            try:
                from app.services.rigidity_calculator import RigidityCalculator
                ld_ratio = rigidity_info.get('ld_ratio', 0)
                operation = context.operation or 'токарка'
                op_type = "milling" if "фрезер" in (operation or "").lower() else "turning"
                strategies = RigidityCalculator.get_anti_chatter_strategy(ld_ratio, op_type)
                for strategy in strategies[:5]:
                    lines.append(f"• {strategy}")
            except Exception as e:
                logger.debug(f"Could not get anti-chatter strategies: {e}")
    if context.assumptions_made:
        lines.append("")
        lines.append(t('rec.assumed', lang=lang))
        for assumption in context.assumptions_made:
            metadata = context.get_field_metadata(assumption)
            if metadata and metadata.reasoning:
                lines.append(f"• {assumption}: {metadata.reasoning}")
    lines.append("")
    lines.append(t('rec.ask_practice', lang=lang))
    lines.append(t('rec.ask_practice_hint', lang=lang))
    lines.append(t('rec.ask_vibration_photo', lang=lang))
    return "\n".join(lines)


# ============================================================================
# ФУНКЦИИ ДЛЯ СОЗДАНИЯ КЛАВИАТУР
# ============================================================================

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


def format_clarification_request(context: Context, missing_fields: list) -> str:
    """Форматировать запрос на уточнение в естественном виде."""
    lines = []
    
    lines.append("🤔 <b>Нужно уточнить несколько моментов:</b>")
    lines.append("")
    
    if 'material' in missing_fields:
        lines.append("• <b>Из какого материала</b> заготовка? (сталь, алюминий, нержавейка...)")
    
    if 'diameter_start' in missing_fields or 'diameter_end' in missing_fields:
        lines.append("• <b>Какие диаметры?</b> (например: с Ø100 до Ø90)")
    
    if 'operation' in missing_fields:
        lines.append("• <b>Какая операция?</b> (черновая, чистовая...)")
    
    # Показываем что уже известно
    known = format_context_summary(context)
    if known and known != "Пока нет данных...":
        lines.append("")
        lines.append("<b>Что я уже знаю:</b>")
        lines.append(known)
    
    lines.append("")
    lines.append("💬 <i>Можете описать всё в одном сообщении, я пойму.</i>")
    
    return "\n".join(lines)


# ============================================================================
# ОБРАБОТЧИКИ СООБЩЕНИЙ
# ============================================================================

@dp.message(Command("reset"))
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


@dp.message(Command("status"))
async def cmd_status(message: types.Message, state: FSMContext):
    """Показать текущее состояние контекста."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    
    # Получаем контекст
    context = None
    if context_manager:
        context = context_manager.get(user_id)
    if not context and file_storage:
        context = file_storage.get(user_id)
    if not context:
        context = user_contexts.get(user_id)
    
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


@dp.message(Command("history"))
async def cmd_history(message: types.Message, state: FSMContext):
    """Показать историю диалога."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    
    # Получаем контекст
    context = None
    if context_manager:
        context = context_manager.get(user_id)
    if not context and file_storage:
        context = file_storage.get(user_id)
    if not context:
        context = user_contexts.get(user_id)
    
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


@dp.message(Command("calc", "calculator", "калькулятор"))
async def cmd_calc(message: types.Message, state: FSMContext):
    """Запустить простой калькулятор режимов резания."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    
    await state.set_state(CalculatorStates.waiting_operation)
    
    await message.answer(
        "🔧 <b>Простой калькулятор режимов резания</b>\n\n"
        "Выберите тип обработки:\n"
        "• <b>точение</b> или <b>turning</b>\n"
        "• <b>фрезерование</b> или <b>milling</b>\n\n"
        "Или напишите <b>/cancel</b> для отмены."
    )


@dp.message(CalculatorStates.waiting_operation)
async def calc_handle_operation(message: types.Message, state: FSMContext):
    """Обработка выбора типа обработки."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    text = (message.text or "").lower().strip()
    
    # Определяем тип обработки
    if "точение" in text or "turning" in text or text == "1":
        operation = "turning"
    elif "фрезерование" in text or "milling" in text or text == "2":
        operation = "milling"
    else:
        await message.answer(
            "❌ Неверный выбор. Укажите:\n"
            "• <b>точение</b> или <b>turning</b>\n"
            "• <b>фрезерование</b> или <b>milling</b>"
        )
        return
    
    # Сохраняем операцию
    await state.update_data(calc_operation=operation)
    await state.set_state(CalculatorStates.waiting_material)
    
    # Получаем список материалов из knowledge_service
    materials_list = []
    if knowledge_service:
        materials_list = list(knowledge_service.materials.keys())[:10]  # Первые 10
    
    materials_text = ""
    if materials_list:
        materials_text = "\n\nДоступные материалы:\n" + "\n".join(f"• {m}" for m in materials_list[:5])
    
    await message.answer(
        f"✅ Операция: <b>{'Точение' if operation == 'turning' else 'Фрезерование'}</b>\n\n"
        f"📦 Укажите материал (например: сталь, алюминий, титан){materials_text}\n\n"
        "Или напишите <b>/cancel</b> для отмены."
    )


@dp.message(CalculatorStates.waiting_material)
async def calc_handle_material(message: types.Message, state: FSMContext):
    """Обработка выбора материала."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    text = (message.text or "").strip()
    
    if not text:
        await message.answer("❌ Укажите материал.")
        return
    
    # Сохраняем материал
    await state.update_data(calc_material=text)
    await state.set_state(CalculatorStates.waiting_machine)
    
    # Получаем список станков
    machines_list = []
    if knowledge_service:
        machines_list = list(knowledge_service.machines.keys())[:10]
    
    machines_text = ""
    if machines_list:
        machines_text = "\n\nДоступные станки:\n" + "\n".join(f"• {m}" for m in machines_list[:5])
    
    await message.answer(
        f"✅ Материал: <b>{text}</b>\n\n"
        f"🏭 Укажите тип станка (например: токарный ЧПУ, фрезерный станок){machines_text}\n\n"
        "Или напишите <b>/cancel</b> для отмены."
    )


@dp.message(CalculatorStates.waiting_machine)
async def calc_handle_machine(message: types.Message, state: FSMContext):
    """Обработка выбора станка и расчет."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    text = (message.text or "").strip()
    
    if not text:
        await message.answer("❌ Укажите станок.")
        return
    
    # Получаем сохраненные данные
    data = await state.get_data()
    operation = data.get("calc_operation", "turning")
    material = data.get("calc_material", "")
    
    if not material:
        await message.answer("❌ Ошибка: материал не найден. Начните заново с /calc")
        await state.clear()
        return
    
    # Создаем калькулятор
    calculator = SimpleCalculator(knowledge_service)
    
    # Формируем входные данные
    calc_input = SimpleCalculatorInput(
        operation=operation,
        material=material,
        machine_type=text,
        diameter_mm=None,  # Можно будет добавить опциональный ввод
        tool_radius_mm=None,  # Можно будет добавить опциональный ввод
        mode="normal"
    )
    
    try:
        # Рассчитываем режимы
        result = calculator.calculate(calc_input)
        
        # Форматируем результат
        result_text = (
            f"📊 <b>Результаты расчета:</b>\n\n"
            f"⚙️ Операция: <b>{'Точение' if operation == 'turning' else 'Фрезерование'}</b>\n"
            f"📦 Материал: <b>{material}</b>\n"
            f"🏭 Станок: <b>{text}</b>\n\n"
            f"📈 <b>Режимы резания:</b>\n"
            f"• Скорость резания: <b>{result.vc_m_min} м/мин</b>\n"
            f"• Обороты: <b>{result.rpm} об/мин</b>\n"
            f"• Подача: <b>{result.feed_mm_rev} мм/об</b>\n"
            f"• Глубина резания: <b>{result.ap_mm} мм</b>\n"
            f"• Скорость подачи: <b>{result.feed_rate_mm_min} мм/мин</b>\n"
            f"• Мощность резания: <b>{result.power_kw} кВт</b>\n"
        )
        
        if result.warnings:
            result_text += "\n⚠️ <b>Предупреждения:</b>\n"
            for warning in result.warnings:
                result_text += f"• {warning}\n"
        
        await message.answer(result_text)
        
    except Exception as e:
        logger.error(f"Error calculating modes: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>Ошибка расчета</b>\n\n"
            f"Произошла ошибка при расчете режимов: {str(e)}\n\n"
            f"Попробуйте еще раз с командой /calc"
        )
    
    # Очищаем состояние
    await state.clear()


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отменить текущую операцию."""
    user_id = str(message.from_user.id)
    lang = get_lang(None, user_id)
    
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Операция отменена.")
    else:
        await message.answer("ℹ️ Нет активной операции для отмены.")


@dp.message(Command("stats"))
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


@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Начало работы с ботом - полный reset."""
    await state.clear()
    
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name or "друг"
    
    # ПОЛНЫЙ RESET при /start
    # Удаляем контекст из всех хранилищ
    if context_manager:
        context_manager.delete(user_id)
    if file_storage:
        file_storage.delete(user_id)
    if context_repository:
        try:
            # Удаляем контекст из репозитория если есть метод delete
            if hasattr(context_repository, 'delete'):
                context_repository.delete(user_id)
            elif hasattr(context_repository, 'clear_context'):
                context_repository.clear_context(user_id)
        except Exception as e:
            logger.warning(f"Could not delete context from repository: {e}")
    if user_id in user_contexts:
        del user_contexts[user_id]
    
    # Проверяем, есть ли история у пользователя (только для информации, не восстанавливаем)
    if context_repository:
        try:
            existing_context = context_repository.get_context(user_id)
        except:
            existing_context = None
    else:
        existing_context = None
    
    has_history = existing_context and (
        existing_context.dialog_history or
        existing_context.material or
        existing_context.machine_type or
        existing_context.tool_name
    )
    
    # НЕ показываем старую работу - всегда чистое приветствие
    if False and has_history:  # Отключено - всегда чистое приветствие
        # Есть история - предлагаем продолжить или начать заново
        welcome_text = (
            f"👋 <b>Привет, {user_name}!</b>\n\n"
            f"📋 <b>Я помню нашу предыдущую работу:</b>\n\n"
        )
        
        # Показываем что уже известно
        if existing_context.machine_type:
            # Проверяем, не является ли это неизвестным станком (не стандартный тип)
            known_types = ['токарный чпу', 'токарный ручной', 'фрезерный чпу', 'фрезерный ручной']
            if existing_context.machine_type.lower() not in known_types:
                welcome_text += f"🏭 <b>Станок:</b> {existing_context.machine_type} <i>(сохранён в базу)</i>\n"
            else:
                welcome_text += f"🏭 <b>Станок:</b> {existing_context.machine_type}\n"
        
        if existing_context.material:
            # Проверяем, не является ли это неизвестным материалом
            known_materials = ['сталь', 'алюминий', 'нержавейка', 'титан', 'чугун', 'латунь', 'медь']
            if existing_context.material.lower() not in known_materials:
                welcome_text += f"🔩 <b>Материал:</b> {existing_context.material} <i>(сохранён в базу)</i>\n"
            else:
                welcome_text += f"🔩 <b>Материал:</b> {existing_context.material}\n"
        
        if existing_context.tool_name:
            welcome_text += f"🔧 <b>Инструмент:</b> {existing_context.tool_name}\n"
        if existing_context.diameter_start and existing_context.diameter_end:
            welcome_text += f"📏 <b>Диаметры:</b> Ø{existing_context.diameter_start} → Ø{existing_context.diameter_end} мм\n"
        
        welcome_text += (
            "\n💬 <b>Что хотите сделать?</b>\n\n"
            "• Опишите новую задачу обработки\n"
            "• Добавить/изменить инструмент (или отправьте фото)\n"
            "• Изменить параметры станка\n"
            "• Начать с чистого листа (/start для нового контекста)\n\n"
            "<i>Используйте кнопки ниже или напишите что нужно.</i>"
        )
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
        # Новая сессия — приветствие с предложением собрать информацию
        welcome_text = (
            f"👋 <b>Привет, {user_name}!</b>\n\n"
            f"Я <b>CNC Assistant</b> — помощник по режимам резания для токарки и фрезеровки.\n\n"
            f"📋 <b>Что умею:</b>\n"
            f"• Подбирать обороты, подачи, глубины резания\n"
            f"• Калькулятор режимов резания (без стандартов)\n"
            f"• Работать по ГОСТ/ОСТ (болты, гайки и т.п.)\n"
            f"• Распознавать технологический маршрут (расточка, сверление, фрезер)\n"
            f"• Сохранять работы и загружать по номеру\n"
            f"• Искать информацию в интернете, если чего-то не знаю\n\n"
        )
        
        # Проверяем, есть ли информация о станке и инструменте
        has_machine = existing_context and existing_context.machine_type
        has_tool = existing_context and existing_context.tool_name
        
        if not has_machine or not has_tool:
            # Предлагаем собрать информацию
            welcome_text += (
                f"💡 <b>Чтобы подбор режимов был точнее, укажите:</b>\n\n"
            )
            
            missing_items = []
            if not has_machine:
                missing_items.append("станок (название или тип)")
            if not has_tool:
                missing_items.append("инструмент")
            
            if missing_items:
                welcome_text += f"📝 <b>Нужно:</b> {', '.join(missing_items)}\n\n"
            
            if not has_machine:
                welcome_text += (
                    f"🏭 <b>По станку:</b> можно написать одним сообщением название, мощность (кВт) и макс. обороты (об/мин). "
                    f"Например: <code>NEF500 15 кВт 3000 об/мин</code> или просто <code>токарный ЧПУ</code> — потом уточним мощность.\n\n"
                )
            
            welcome_text += (
                f"🔧 <b>Команды:</b> <code>помощь</code> · <code>мои работы</code> · <code>история</code>\n\n"
                f"<i>Используйте кнопки ниже или напишите текст.</i>"
            )
            
            # Создаем клавиатуру для сбора информации
            buttons = []
            if not has_machine:
                buttons.append([InlineKeyboardButton(text="🏭 Указать станок", callback_data="select_machine")])
            if not has_tool:
                buttons.append([InlineKeyboardButton(text="🔧 Указать инструмент", callback_data="select_tool")])
            
            if buttons:
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await message.answer(welcome_text, reply_markup=keyboard)
            else:
                await message.answer(welcome_text)
        else:
            # Вся информация есть - стандартное приветствие
            welcome_text += (
                f"💬 <b>Что написать:</b>\n"
                f"• Задача: <code>сталь Ø100→90 черновая</code>, <code>титан с Ø200 до Ø50</code>\n"
                f"• Калькулятор: <code>2+2</code>, <code>120*3.14</code>, <code>sqrt(16)</code>\n"
                f"• Стандарт: <code>ОСТ 33057-80</code>, <code>ГОСТ 7798</code>\n"
                f"• Или отправь фото инструмента\n\n"
                f"<i>Используйте кнопки ниже или напишите что нужно.</i>"
            )
            await message.answer(welcome_text, reply_markup=create_main_nav_keyboard())


@dp.message(Command("lang"))
async def cmd_lang(message: types.Message, state: FSMContext):
    """Смена языка интерфейса."""
    user_id = str(message.from_user.id)
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    lang = get_lang(context)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t('lang.ru', 'ru'), callback_data="lang_ru"),
            InlineKeyboardButton(text=t('lang.en', 'en'), callback_data="lang_en"),
            InlineKeyboardButton(text=t('lang.zh', 'zh'), callback_data="lang_zh"),
        ]
    ])
    await message.answer(t('lang.choose', lang=lang), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("lang_"))
async def handle_lang_callback(callback: types.CallbackQuery, state: FSMContext):
    """Установить язык по кнопке."""
    await callback.answer()
    lang = callback.data.replace("lang_", "")
    if lang not in SUPPORTED_LANGS:
        return
    user_id = str(callback.from_user.id)
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    if not context:
        context = Context(user_id=user_id)
        if context_repository:
            context_repository.save_context(user_id, context)
        else:
            user_contexts[user_id] = context
    context.lang = lang
    save_context_safe(context, user_id)
    name = t('lang.' + lang, lang)
    await callback.message.answer(t('lang.saved', lang=lang, name=name))


def _parse_modes_from_caption(caption: Optional[str]) -> Dict[str, float]:
    """Из подписи извлечь n, ap, f, z. Пример: 'n=1200 ap=2 f=0.2 z=4' или 'n 1200 ap 2'."""
    out = {"rpm": 1000.0, "ap_mm": 2.0, "feed_mm_rev": 0.2, "teeth_count": 1}
    if not caption or not caption.strip():
        return out
    # n=1200, n = 1200, n 1200
    for pat, key in [
        (r"[nN]\s*[=:]\s*(\d+[.,]?\d*)", "rpm"),
        (r"[nN]\s+(\d+[.,]?\d*)", "rpm"),
        (r"[aA][pP]\s*[=:]\s*(\d+[.,]?\d*)", "ap_mm"),
        (r"[aA][pP]\s+(\d+[.,]?\d*)", "ap_mm"),
        (r"\b[fF]\s*[=:]\s*(\d+[.,]?\d*)", "feed_mm_rev"),
        (r"\b[fF]\s+(\d+[.,]?\d*)", "feed_mm_rev"),
        (r"[zZ]\s*[=:]\s*(\d+)", "teeth_count"),
        (r"[zZ]\s+(\d+)", "teeth_count"),
    ]:
        m = re.search(pat, caption)
        if m:
            try:
                val = float(m.group(1).replace(",", "."))
                if key == "teeth_count":
                    val = int(val)
                out[key] = val
            except ValueError:
                pass
    return out


@dp.message(F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Обработка фотографий: инструмент или спектр вибрации (по состоянию)."""
    import time
    start_time = time.time()
    
    user_id = str(message.from_user.id)
    current_state = await state.get_state()
    
    # Rate limiting (используем async версию если доступна, иначе sync)
    if rate_limiter:
        if inspect.iscoroutinefunction(rate_limiter.is_allowed):
            is_allowed = await rate_limiter.is_allowed(user_id)
        else:
            is_allowed = rate_limiter.is_allowed_sync(user_id)
        
        if not is_allowed:
            if inspect.iscoroutinefunction(rate_limiter.get_remaining_time):
                remaining_time = await rate_limiter.get_remaining_time(user_id)
            else:
                remaining_time = rate_limiter.get_remaining_time_sync(user_id)
            
            await message.answer(
                f"⏳ <b>Слишком много сообщений</b>\n\n"
                f"Пожалуйста, подождите {int(remaining_time)} секунд перед отправкой следующего сообщения."
            )
            return
    
    # Обновляем метрики
    metrics.total_photos += 1

    # Если ожидаем фото спектра для анализа вибрации
    if current_state and "waiting_photo" in (current_state or ""):
        try:
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            image_data = await bot.download_file(file.file_path)
            image_bytes = image_data.read()
        except Exception as e:
            logger.warning(f"Download vibration photo failed: {e}")
            await message.answer("❌ Не удалось загрузить фото. Попробуйте ещё раз.")
            return

        if not image_parser or not image_parser.ocr_available:
            await state.clear()
            await message.answer(
                "⚠️ OCR не настроен. Установите Tesseract для распознавания спектра.",
                reply_markup=create_main_nav_keyboard(),
            )
            return

        try:
            from app.services.vibration_analyzer import (
                analyze_vibration_from_image,
                CurrentModes,
            )
            modes_dict = _parse_modes_from_caption(message.caption)
            current_modes = CurrentModes(
                rpm=modes_dict["rpm"],
                ap_mm=modes_dict["ap_mm"],
                feed_mm_rev=modes_dict["feed_mm_rev"],
                teeth_count=int(modes_dict["teeth_count"]) if modes_dict["teeth_count"] >= 1 else 1,
            )
            session = None
            try:
                session = get_session(DB_URL)
                result = analyze_vibration_from_image(
                    image_bytes,
                    current_modes,
                    image_parser,
                    tolerance=0.05,
                    db_session=session,
                )
            finally:
                if session:
                    try:
                        session.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.exception("Vibration analysis failed")
            await state.clear()
            await message.answer(
                f"❌ Ошибка анализа: {e}",
                reply_markup=create_main_nav_keyboard(),
            )
            return

        await state.clear()
        if not result.success:
            await message.answer(
                f"❌ <b>Анализ вибрации</b>\n\n{result.error}\n\n"
                "💡 Убедитесь, что на фото виден спектр/FFT с подписью частоты (Hz). "
                "В подписи к фото можно указать режимы: <code>n=1200 ap=2 f=0.2 z=4</code>",
                reply_markup=create_main_nav_keyboard(),
            )
            return

        lines = [
            "📈 <b>Анализ вибрации</b>",
            "",
            f"🔍 <b>Тип:</b> {result.problem_type_ru}",
            f"📊 Частота на спектре: <b>{result.f_measured_hz:.1f} Гц</b>",
            f"🔄 f_шпиндель = n/60 = <b>{result.f_spindle_hz:.1f} Гц</b>",
            f"🦷 f_зубовая = f_шп × z = <b>{result.f_tooth_hz:.1f} Гц</b>",
            "",
        ]
        if result.new_rpm is not None or result.new_ap_mm is not None or result.new_feed_mm_rev is not None:
            lines.append("📐 <b>Рекомендуемые режимы:</b>")
            if result.new_rpm is not None:
                lines.append(f"  • Обороты: <b>{result.new_rpm:.0f}</b> об/мин")
            if result.new_ap_mm is not None:
                lines.append(f"  • Глубина ap: <b>{result.new_ap_mm:.2f}</b> мм")
            if result.new_feed_mm_rev is not None:
                lines.append(f"  • Подача f: <b>{result.new_feed_mm_rev:.3f}</b> мм/об")
            lines.append("")
        for rec in result.recommendations:
            lines.append(f"• {rec}")
        await message.answer(
            "\n".join(lines),
            reply_markup=create_main_nav_keyboard(),
        )
        return

    # Обычный поток: фото инструмента
    if context_repository:
        context = context_repository.get_context(user_id)
        if not context:
            context = Context()
            context.user_id = user_id
            context_repository.save_context(context)
    else:
        context = user_contexts.get(user_id)
        if not context:
            context = Context()
            context.user_id = user_id
            user_contexts[user_id] = context

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        image_data = await bot.download_file(file.file_path)
        image_bytes = image_data.read()

        if not image_parser:
            await message.answer(
                "❌ OCR не настроен. Установите pytesseract и Pillow для распознавания фотографий."
            )
            return
        
        # Проверяем, что OCR доступен перед парсингом (graceful degradation)
        if not image_parser or not image_parser.ocr_available:
            await message.answer(
                "📸 <b>OCR временно недоступен</b>\n\n"
                "Пожалуйста, опишите инструмент текстом:\n"
                "• Тип инструмента (CNMG, WNMG...)\n"
                "• Производитель (Sandvik, Iscar...)\n"
                "• Радиус пластины (0.4, 0.8 мм)\n\n"
                "💡 <i>Или установите Tesseract OCR для распознавания фотографий.</i>"
            )
            return
        
        try:
            parse_result = image_parser.parse_tool_image(image_bytes)
        except Exception as ocr_error:
            logger.error(f"OCR error: {ocr_error}", exc_info=True)
            metrics.total_errors += 1
            
            # Graceful degradation - предлагаем текстовый ввод
            if 'tesseract' in str(ocr_error).lower() or 'TesseractNotFoundError' in str(type(ocr_error)):
                await message.answer(
                    "❌ <b>Tesseract OCR не установлен</b>\n\n"
                    "Для распознавания фотографий установите Tesseract OCR:\n"
                    "• Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "• Linux: sudo apt-get install tesseract-ocr\n\n"
                    "💡 <i>А пока опишите инструмент текстом.</i>"
                )
            else:
                await message.answer(
                    "⚠️ <b>Не удалось распознать фото</b>\n\n"
                    "Попробуйте сфотографировать чётче или опишите инструмент текстом."
                )
            return
        
        if not parse_result.get('success'):
            # Обработка ошибок парсинга
            error_message = parse_result.get('error', 'Не удалось распознать инструмент на фотографии.')
            metrics.total_errors += 1
            
            if 'tesseract' in error_message.lower() or 'ocr' in error_message.lower():
                await message.answer(
                    "❌ <b>Tesseract OCR не установлен</b>\n\n"
                    "Для распознавания фотографий установите Tesseract OCR:\n"
                    "• Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "• Linux: sudo apt-get install tesseract-ocr\n\n"
                    "💡 <i>А пока опишите инструмент текстом.</i>"
                )
            else:
                await message.answer(
                    f"⚠️ <b>Не удалось распознать фото</b>\n\n"
                    f"Попробуйте сфотографировать чётче или опишите инструмент текстом."
                )
            return
        
        if parse_result.get('success'):
            # Сохраняем инструмент в БД
            tool_id = None
            if handler and handler.tool_saver:
                tool_id = handler.tool_saver.save_tool_from_image(parse_result)
            
            # Название для отображения: сначала ISO/распознанное имя, иначе — текст с фото (OCR)
            tool_name_recognized = parse_result.get('tool_name')
            if not tool_name_recognized:
                raw = (parse_result.get('extracted_text') or '').strip()
                # Берём первую непустую строку или первые 60 символов
                first_line = next((ln.strip() for ln in raw.replace('\r', '\n').split('\n') if ln.strip()), '')
                if first_line:
                    tool_name_recognized = first_line[:60].strip() if len(first_line) > 60 else first_line
                else:
                    tool_name_recognized = raw[:60].strip() if raw else None
            if not tool_name_recognized:
                tool_name_recognized = 'Инструмент с фото'
            
            # Обновляем контекст (всегда записываем то, что показываем пользователю)
            context.set_field(
                'tool_name',
                tool_name_recognized,
                DataSource.USER,
                confidence=parse_result.get('confidence', 0.7),
                reasoning="Распознано с фотографии инструмента"
            )
            
            # Записываем в историю, чтобы инструмент появлялся в «Мои инструменты»
            context.add_to_history('tool_saved', {
                'tool_name': tool_name_recognized,
                'tool_id': tool_id,
            })
            
            if parse_result.get('tool_type'):
                context.set_field(
                    'tool_type',
                    parse_result['tool_type'],
                    DataSource.USER,
                    confidence=parse_result.get('confidence', 0.7),
                    reasoning="Определено по ISO коду"
                )
            
            if parse_result.get('insert_material'):
                context.set_field(
                    'tool_material',
                    parse_result['insert_material'],
                    DataSource.USER,
                    confidence=parse_result.get('confidence', 0.7),
                    reasoning="Распознано с фотографии"
                )
            
            # Формируем ответ — явно показываем, какой номер/маркировку распознали
            response_lines = []
            response_lines.append("✅ <b>Инструмент распознан!</b>")
            response_lines.append("")
            response_lines.append(f"📌 <b>Распознал номер/маркировку:</b> <code>{tool_name_recognized}</code>")
            response_lines.append("")
            
            if parse_result.get('tool_type'):
                response_lines.append(f"🔧 <b>Тип:</b> {parse_result['tool_type']}")
            
            if parse_result.get('manufacturer'):
                response_lines.append(f"🏭 <b>Производитель:</b> {parse_result['manufacturer']}")
            
            if parse_result.get('insert_material'):
                response_lines.append(f"💎 <b>Материал:</b> {parse_result['insert_material']}")
            
            response_lines.append("")
            response_lines.append("💾 <i>Записал в «Мои инструменты» — увидишь по кнопке ниже.</i>")
            if tool_id:
                response_lines.append(f"<i>В базе под ID: {tool_id}</i>")
            response_lines.append("")
            response_lines.append("💬 <b>Теперь опиши задачу обработки, и я учту этот инструмент.</b>")
            
            await message.answer(
                "\n".join(response_lines),
                reply_markup=create_main_nav_keyboard(lang=get_lang(context))
            )
            
            # Сохраняем контекст (с проверкой user_id)
            save_context_safe(context, user_id)
        
        else:
            error = parse_result.get('error', 'Не удалось распознать')
            await message.answer(
                f"❌ <b>Не удалось распознать инструмент</b>\n\n"
                f"Ошибка: {error}\n\n"
                f"💡 <i>Попробуйте сфотографировать этикетку или маркировку инструмента более чётко.</i>"
            )
    
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        metrics.total_errors += 1
        await message.answer(
            f"❌ <b>Ошибка обработки фотографии</b>\n\n"
            f"Попробуйте ещё раз или опишите инструмент текстом."
        )
    finally:
        # Обновляем метрики времени ответа (используем sync версию для обратной совместимости)
        response_time = time.time() - start_time
        if hasattr(metrics, 'add_response_time_sync'):
            metrics.add_response_time_sync(response_time)
        else:
            metrics.add_response_time(response_time)


# ============================================================================
# ОБРАБОТЧИКИ CALLBACK QUERY (КНОПКИ)
# ============================================================================

@dp.callback_query(F.data == "continue_work")
async def handle_continue_work(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Продолжить' после загрузки работы."""
    try:
        await callback.answer()
        user_id = str(callback.from_user.id)
        
        logger.info(f"Continue work button pressed by user {user_id}")
        
        # Получаем контекст
        context = None
        if context_repository:
            try:
                context = context_repository.get_context(user_id)
            except Exception as e:
                logger.error(f"Error getting context from repository: {e}", exc_info=True)
        
        if not context:
            context = user_contexts.get(user_id)
        
        if not context:
            logger.warning(f"Context not found for user {user_id}")
            await callback.message.answer("❌ Контекст не найден. Начните с команды /start", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Начать", callback_data="new_task")]]))
            return
        
        # Обрабатываем как будто пользователь написал "давай"
        if handler:
            try:
                result = await handler.process_message(
                    user_text="давай",
                    user_id=user_id,
                    session_id=context.session_id,
                    existing_context=context
                )
                await process_handler_result(result, callback.message, context, user_id)
            except Exception as e:
                logger.error(f"Error processing continue work: {e}", exc_info=True)
                await callback.message.answer(
                    "❌ <b>Ошибка при обработке запроса.</b>\n\n"
                    "Попробуйте описать задачу текстом.",
                    reply_markup=create_main_nav_keyboard()
                )
        else:
            logger.error("Handler not available")
            await callback.message.answer("❌ Обработчик недоступен.", reply_markup=create_main_nav_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_continue_work: {e}", exc_info=True)
        try:
            await callback.message.answer(
                "❌ <b>Ошибка при обработке кнопки.</b>\n\n"
                "Попробуйте описать задачу текстом или используйте кнопки ниже.",
                reply_markup=create_main_nav_keyboard()
            )
        except Exception:
            pass


@dp.callback_query(F.data.startswith("material_"))
async def handle_material_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора материала."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    material = callback.data.replace("material_", "")
    
    if material == "manual":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help")],
        ])
        await callback.message.answer("✏️ <b>Введите материал вручную:</b>\n\nНапример: сталь, алюминий, титан, нержавейка...", reply_markup=kb)
        return
    
    # Получаем контекст
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    
    if not context:
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if context_repository:
            context_repository.save_context(context)
        else:
            user_contexts[user_id] = context
    
    # Устанавливаем материал
    from app.core.context import DataSource
    context.set_field('material', material, DataSource.USER, confidence=1.0, reasoning="Выбрано из кнопки")
    save_context_safe(context, user_id)
    
    await callback.message.answer(f"✅ <b>Материал выбран:</b> {material}", reply_markup=create_clarify_keyboard([], context))
    
    # Проверяем, что еще нужно уточнить
    if handler:
        result = await handler.process_message(
            user_text=f"материал {material}",
            user_id=user_id,
            session_id=context.session_id,
            existing_context=context
        )
        # Обрабатываем результат как обычное сообщение
        await process_handler_result(result, callback.message, context, user_id)


@dp.callback_query(F.data.startswith("mode_"))
async def handle_mode_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора режима обработки."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    mode = callback.data.replace("mode_", "")
    
    if mode == "manual":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help")]])
        await callback.message.answer("✏️ <b>Введите режим вручную:</b>\n\nНапример: черновая, получистовая, чистовая, тонкая...", reply_markup=kb)
        return
    
    # Получаем контекст
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    
    if not context:
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if context_repository:
            context_repository.save_context(context)
        else:
            user_contexts[user_id] = context
    
    # Устанавливаем режим
    from app.core.context import DataSource
    context.set_field('mode', mode, DataSource.USER, confidence=1.0, reasoning="Выбрано из кнопки")
    save_context_safe(context, user_id)
    
    await callback.message.answer(f"✅ <b>Режим выбран:</b> {mode}", reply_markup=create_clarify_keyboard([], context))
    
    # Проверяем, что еще нужно уточнить
    if handler:
        result = await handler.process_message(
            user_text=f"режим {mode}",
            user_id=user_id,
            session_id=context.session_id,
            existing_context=context
        )
        await process_handler_result(result, callback.message, context, user_id)


@dp.callback_query(F.data.startswith("machine_"))
async def handle_machine_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора станка."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    machine = callback.data.replace("machine_", "")
    
    if machine == "manual":
        await callback.message.answer(
            "✏️ <b>Введите станок вручную:</b>\n\n"
            "Например: <code>токарный ЧПУ</code>, <code>NEF500</code>, или сразу с параметрами:\n"
            "<code>NEF500 15 кВт 3000 об/мин</code>"
        )
        return
    
    # Получаем контекст
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    
    if not context:
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if context_repository:
            context_repository.save_context(context)
        else:
            user_contexts[user_id] = context
    
    # Устанавливаем станок
    from app.core.context import DataSource
    context.set_field('machine_type', machine, DataSource.USER, confidence=1.0, reasoning="Выбрано из кнопки")
    save_context_safe(context, user_id)
    
    await callback.message.answer(f"✅ <b>Станок выбран:</b> {machine}", reply_markup=create_post_machine_keyboard())
    
    # Спрашиваем мощность и обороты, если не известны (для типов типа "токарный ЧПУ" в базе их нет)
    machine_info = handler.knowledge_service.find_machine(machine) if handler else None
    has_power_rpm = machine_info and (getattr(machine_info, "power_kw", None) or getattr(machine_info, "max_rpm", None))
    if not has_power_rpm:
        await callback.message.answer(
            "💡 <b>Уточните, если знаете:</b> мощность шпинделя (кВт) и макс. обороты (об/мин).\n"
            "Например: <code>15 кВт, 3000 об/мин</code> — тогда подбор режимов будет точнее."
        )
    
    # Проверяем, нужно ли еще указать инструмент
    if not context.tool_name:
        buttons = []
        buttons.append([InlineKeyboardButton(text="🔧 Указать инструмент", callback_data="select_tool")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.answer(
            "💡 <b>Отлично! Теперь укажите инструмент:</b>\n\n"
            "Вы можете отправить фото инструмента или описать его текстом.",
            reply_markup=keyboard
        )
    
    # Проверяем, что еще нужно уточнить
    if handler:
        result = await handler.process_message(
            user_text=f"станок {machine}",
            user_id=user_id,
            session_id=context.session_id,
            existing_context=context
        )
        await process_handler_result(result, callback.message, context, user_id)


@dp.callback_query(F.data == "select_material")
async def handle_select_material(callback: CallbackQuery, state: FSMContext):
    """Показать клавиатуру выбора материала."""
    await callback.answer()
    keyboard = create_material_keyboard()
    await callback.message.answer("📋 <b>Выберите материал:</b>", reply_markup=keyboard)


@dp.callback_query(F.data == "select_mode")
async def handle_select_mode(callback: CallbackQuery, state: FSMContext):
    """Показать клавиатуру выбора режима."""
    await callback.answer()
    keyboard = create_operation_keyboard()
    await callback.message.answer("⚙️ <b>Выберите режим обработки:</b>", reply_markup=keyboard)


@dp.callback_query(F.data == "select_machine")
async def handle_select_machine(callback: CallbackQuery, state: FSMContext):
    """Показать клавиатуру выбора станка и подсказку про мощность/обороты."""
    await callback.answer()
    keyboard = create_machine_type_keyboard()
    await callback.message.answer(
        "🏭 <b>Выберите станок или введите вручную:</b>\n\n"
        "Можно написать одним сообщением: <b>название, мощность (кВт), макс. обороты (об/мин)</b>.\n"
        "Например: <code>NEF500 15 кВт 3000 об/мин</code>",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "nav_calculator")
async def handle_nav_calculator(callback: CallbackQuery, state: FSMContext):
    """Запустить калькулятор режимов резания."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    lang = get_lang(None, user_id)
    
    await state.set_state(CalculatorStates.waiting_operation)
    
    await callback.message.answer(
        "🧮 <b>Калькулятор режимов резания</b>\n\n"
        "Выберите тип обработки:\n"
        "• <b>точение</b> или <b>turning</b>\n"
        "• <b>фрезерование</b> или <b>milling</b>\n\n"
        "Или напишите <b>/cancel</b> для отмены."
    )


@dp.callback_query(F.data == "nav_vibration")
async def handle_nav_vibration(callback: CallbackQuery, state: FSMContext):
    """Включить режим анализа вибрации по фото спектра."""
    await callback.answer()
    await state.set_state(VibrationStates.waiting_photo)
    await callback.message.answer(
        "📈 <b>Анализ вибрации по фото спектра</b>\n\n"
        "Отправьте фото экрана анализатора / FFT / спектра вибрации.\n\n"
        "Я извлеку пиковую частоту (Hz) и сравню с расчётной (шпиндель, зубовая).\n\n"
        "В подписи к фото можно указать текущие режимы:\n"
        "<code>n=1200 ap=2 f=0.2 z=4</code>\n"
        "(обороты, глубина мм, подача мм/об, число зубьев; для точения z=1)\n\n"
        "Если не укажете — будут использованы значения по умолчанию (n=1000, ap=2, f=0.2, z=1)."
    )


@dp.callback_query(F.data == "nav_help")
async def handle_nav_help(callback: CallbackQuery, state: FSMContext):
    """Показать помощь по кнопке (с учётом языка)."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    if context_repository:
        ctx = context_repository.get_context(user_id)
    else:
        ctx = user_contexts.get(user_id)
    lang = get_lang(ctx)
    help_text = (
        t('help.title', lang=lang) + "\n\n"
        + t('help.main', lang=lang) + "\n\n"
        + t('help.how', lang=lang) + "\n\n"
        + t('help.examples', lang=lang) + "\n\n"
        + t('help.commands', lang=lang) + "\n\n"
        + t('help.just_describe', lang=lang)
    )
    await callback.message.answer(help_text, reply_markup=create_main_nav_keyboard(lang=lang))


@dp.callback_query(F.data == "select_tool")
async def handle_select_tool(callback: CallbackQuery, state: FSMContext):
    """Показать подсказку для указания инструмента."""
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏭 Выбрать станок", callback_data="select_machine")],
        [InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help")],
    ])
    await callback.message.answer(
        "🔧 <b>Укажите инструмент:</b>\n\n"
        "Вы можете:\n"
        "• Отправить фото инструмента (я распознаю маркировку)\n"
        "• Написать название инструмента (например: CNMG 120408, фреза 10 мм)\n"
        "• Указать тип инструмента (токарный проходной, фреза концевая)\n\n"
        "💡 <i>Просто опишите инструмент или отправьте фото.</i>",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "input_diameters")
async def handle_input_diameters(callback: CallbackQuery, state: FSMContext):
    """Запрос ввода диаметров."""
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Материал", callback_data="select_material"),
            InlineKeyboardButton(text="⚙️ Режим", callback_data="select_mode"),
        ],
        [
            InlineKeyboardButton(text="🏭 Станок", callback_data="select_machine"),
            InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help"),
        ],
    ])
    await callback.message.answer(
        "📏 <b>Укажите диаметры:</b>\n\n"
        "Например:\n"
        "• <code>с Ø100 до Ø90</code>\n"
        "• <code>Ø100→90</code>\n"
        "• <code>100 до 90</code>",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "input_text")
async def handle_input_text(callback: CallbackQuery, state: FSMContext):
    """Запрос ввода всех данных текстом."""
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Материал", callback_data="select_material"),
            InlineKeyboardButton(text="📏 Диаметры", callback_data="input_diameters"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Режим", callback_data="select_mode"),
            InlineKeyboardButton(text="🏭 Станок", callback_data="select_machine"),
        ],
        [InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help")],
    ])
    await callback.message.answer(
        "✏️ <b>Опишите задачу текстом:</b>\n\n"
        "Например:\n"
        "<code>сталь Ø100→90 черновая токарный ЧПУ</code>\n\n"
        "Я пойму и извлеку все параметры.",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "save_work")
async def handle_save_work(callback: CallbackQuery, state: FSMContext):
    """Сохранить текущую работу."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    
    # Получаем контекст
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    
    if not context:
        await callback.message.answer("❌ Контекст не найден.", reply_markup=create_main_nav_keyboard())
        return
    
    # Сохраняем работу
    if handler and handler.work_manager:
        work_number = handler.work_manager.create_work(user_id, description="Работа с расчетом", context=context)
        if work_number:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📋 Мои работы", callback_data="list_works"),
                    InlineKeyboardButton(text="🔧 Мои инструменты", callback_data="list_tools"),
                    InlineKeyboardButton(text="🔄 Новая задача", callback_data="new_task"),
                ],
                [InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help")],
            ])
            await callback.message.answer(f"✅ <b>Работа сохранена!</b>\n\nНомер работы: <code>{work_number}</code>\n\nИспользуйте <code>работа {work_number}</code> или кнопку ниже.", reply_markup=kb)
        else:
            await callback.message.answer("❌ Не удалось сохранить работу.", reply_markup=create_main_nav_keyboard())
    else:
        await callback.message.answer("❌ Сервис сохранения работ недоступен.", reply_markup=create_main_nav_keyboard())


@dp.callback_query(F.data == "new_task")
async def handle_new_task(callback: CallbackQuery, state: FSMContext):
    """Начать новую задачу."""
    try:
        logger.info(f"handle_new_task called, callback.data={callback.data}, user_id={callback.from_user.id}")
        await callback.answer("Создаю новую задачу...")
        user_id = str(callback.from_user.id)
        
        logger.info(f"Creating new task for user {user_id}")
        
        # Создаем новый контекст
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Сохраняем контекст
        if context_repository:
            try:
                context_repository.save_context(context)
                logger.info(f"Context saved to repository for user {user_id}")
            except Exception as e:
                logger.error(f"Error saving context to repository: {e}", exc_info=True)
                # Fallback на user_contexts
                user_contexts[user_id] = context
        else:
            user_contexts[user_id] = context
            logger.info(f"Context saved to user_contexts for user {user_id}")
        
        # Создаем клавиатуру
        try:
            keyboard = create_clarify_keyboard(['material', 'diameter_start', 'diameter_end'], context)
        except Exception as e:
            logger.error(f"Error creating keyboard: {e}", exc_info=True)
            keyboard = None
        
        # Отправляем сообщение
        message_text = (
            "🆕 <b>Новая задача создана!</b>\n\n"
            "💬 <b>Опишите задачу:</b>\n"
            "• Материал (сталь, алюминий, титан...)\n"
            "• Диаметры (с Ø100 до Ø90)\n"
            "• Тип обработки (черновая, чистовая)\n"
            "• Станок (если известен)\n\n"
            "<i>Или используйте кнопки ниже для выбора параметров.</i>"
        )
        
        if keyboard:
            await callback.message.answer(message_text, reply_markup=keyboard)
        else:
            await callback.message.answer(message_text, reply_markup=create_clarify_keyboard([], context) if context else create_main_nav_keyboard())
        
        logger.info(f"New task message sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in handle_new_task: {e}", exc_info=True)
        try:
            await callback.message.answer(
                "❌ <b>Ошибка при создании новой задачи.</b>\n\n"
                "Попробуйте /start или опишите задачу текстом.",
                reply_markup=create_main_nav_keyboard()
            )
        except:
            pass


@dp.callback_query(F.data == "show_history")
async def handle_show_history(callback: CallbackQuery, state: FSMContext):
    """Показать историю."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    
    # Получаем контекст
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    
    if not context:
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if context_repository:
            context_repository.save_context(context)
        else:
            user_contexts[user_id] = context
    
    # Показываем историю диалога
    response_lines = ["📜 <b>История диалога:</b>\n"]
    
    if context.dialog_history:
        recent_history = context.dialog_history[-10:]  # Последние 10 событий
        for i, event in enumerate(recent_history, 1):
            event_type = event.get('event', 'unknown')
            event_data = event.get('data', {})
            
            if event_type == 'user_message':
                text = event_data.get('text', '')
                if isinstance(text, dict):
                    text = str(text)
                response_lines.append(f"{i}. 👤 <b>Вы:</b> {text[:100]}")
            elif event_type == 'calculation':
                response_lines.append(f"{i}. 🧮 <b>Расчет выполнен</b>")
            elif event_type == 'tool_saved':
                tool_name = event_data.get('tool_name', '')
                response_lines.append(f"{i}. 🔧 <b>Инструмент сохранен:</b> {tool_name}")
        
        if len(context.dialog_history) > 10:
            response_lines.append(f"\n<i>... и ещё {len(context.dialog_history) - 10} событий</i>")
    else:
        response_lines.append("История пуста.")
    
    # Показываем сохраненные работы
    if handler and handler.work_manager:
        works = handler.work_manager.list_works(user_id, limit=10)
        if works:
            response_lines.append("\n\n📋 <b>Ваши сохраненные работы:</b>\n")
            for work in works:
                work_num = work.get('work_number', 'unknown')
                desc = work.get('description', '')
                created = work.get('created_at', '')
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        date_str = dt.strftime('%d.%m.%Y %H:%M')
                    except:
                        date_str = created[:10]
                else:
                    date_str = "неизвестно"
                response_lines.append(f"• <b>{work_num}</b> - {desc or 'Без описания'} (от {date_str})")
            response_lines.append("\n💡 Напишите <code>работа W001</code> или нажмите кнопку ниже.")
        else:
            response_lines.append("\n\n📋 <b>Сохраненных работ пока нет.</b>")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Мои работы", callback_data="list_works"),
            InlineKeyboardButton(text="🔧 Мои инструменты", callback_data="list_tools"),
        ],
        [
            InlineKeyboardButton(text="🔄 Новая задача", callback_data="new_task"),
            InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help"),
        ],
        [
            InlineKeyboardButton(text="🏭 Станок", callback_data="select_machine"),
            InlineKeyboardButton(text="🔧 Инструмент", callback_data="select_tool"),
        ],
    ])
    await callback.message.answer("\n".join(response_lines), reply_markup=keyboard)


@dp.callback_query(F.data.startswith("work_menu_"))
async def handle_work_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню действий для конкретной работы."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    work_number = callback.data.replace("work_menu_", "")
    
    if handler and handler.work_manager:
        work = handler.work_manager.get_work(user_id, work_number)
        if work:
            desc = work.get('description', 'Без описания')
            created = work.get('created_at', '')
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    date_str = dt.strftime('%d.%m.%Y %H:%M')
                except:
                    date_str = created[:10]
            else:
                date_str = "неизвестно"
            
            # Показываем информацию о работе и кнопки действий
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📝 Переименовать", callback_data=f"rename_work_{work_number}"),
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_work_{work_number}")
                ],
                [
                    InlineKeyboardButton(text="📥 Загрузить", callback_data=f"load_work_{work_number}"),
                    InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_work_{work_number}")
                ],
                [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="list_works")]
            ])
            
            await callback.message.answer(
                f"📋 <b>Работа {work_number}</b>\n\n"
                f"📝 <b>Описание:</b> {desc}\n"
                f"📅 <b>Создана:</b> {date_str}\n\n"
                f"💡 <b>Выберите действие:</b>",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer(f"❌ Работа {work_number} не найдена.")
    else:
        await callback.message.answer("❌ Сервис работ недоступен.")


@dp.callback_query(F.data.startswith("rename_work_"))
async def handle_rename_work(callback: CallbackQuery, state: FSMContext):
    """Запросить новое имя для работы."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    work_number = callback.data.replace("rename_work_", "")
    
    # Сохраняем номер работы в состояние для обработки следующего сообщения
    await state.update_data(renaming_work=work_number)
    
    if handler and handler.work_manager:
        work = handler.work_manager.get_work(user_id, work_number)
        if work:
            current_desc = work.get('description', 'Без описания')
            await callback.message.answer(
                f"✏️ <b>Переименование работы {work_number}</b>\n\n"
                f"📝 <b>Текущее имя:</b> {current_desc}\n\n"
                f"💬 <b>Введите новое имя для работы:</b>\n\n"
                f"<i>Или напишите \"отмена\" чтобы отменить.</i>"
            )
        else:
            await callback.message.answer(f"❌ Работа {work_number} не найдена.")
    else:
        await callback.message.answer("❌ Сервис работ недоступен.")


@dp.callback_query(F.data.startswith("edit_work_"))
async def handle_edit_work(callback: CallbackQuery, state: FSMContext):
    """Загрузить работу для редактирования."""
    await callback.answer("Загружаю работу...")
    user_id = str(callback.from_user.id)
    work_number = callback.data.replace("edit_work_", "")
    
    if handler and handler.work_manager:
        loaded_context = handler.work_manager.load_work_to_context(user_id, work_number)
        if loaded_context:
            context = loaded_context
            save_context_safe(context, user_id)
            summary = format_context_summary(context)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить редактирование", callback_data="continue_work")],
                [InlineKeyboardButton(text="💾 Сохранить изменения", callback_data=f"save_work_update_{work_number}")]
            ])
            
            await callback.message.answer(
                f"✏️ <b>Редактирование работы {work_number}</b>\n\n"
                f"{summary}\n\n"
                f"💬 <b>Теперь вы можете:</b>\n"
                f"• Изменить параметры (материал, диаметры, режим и т.д.)\n"
                f"• Продолжить работу с этой задачей\n"
                f"• Сохранить изменения\n\n"
                f"<i>Опишите что нужно изменить или используйте кнопки ниже.</i>",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer(f"❌ Работа {work_number} не найдена.")
    else:
        await callback.message.answer("❌ Сервис работ недоступен.")


@dp.callback_query(F.data.startswith("load_work_"))
async def handle_load_work_button(callback: CallbackQuery, state: FSMContext):
    """Загрузить работу по кнопке."""
    await callback.answer("Загружаю работу...")
    user_id = str(callback.from_user.id)
    work_number = callback.data.replace("load_work_", "")
    
    if handler and handler.work_manager:
        loaded_context = handler.work_manager.load_work_to_context(user_id, work_number)
        if loaded_context:
            context = loaded_context
            save_context_safe(context, user_id)
            summary = format_context_summary(context)
            
            has_data = bool(
                context.material or 
                context.diameter_start or 
                context.diameter_end or 
                context.operation or
                context.standard_id
            )
            
            keyboard = create_continue_keyboard(lang=get_lang(context))
            
            if has_data:
                await callback.message.answer(
                    f"✅ <b>Работа {work_number} загружена!</b>\n\n"
                    f"{summary}\n\n"
                    f"💬 <i>Можете продолжить работу с этой задачей или описать что нужно сделать.</i>",
                    reply_markup=keyboard
                )
            else:
                await callback.message.answer(
                    f"✅ <b>Работа {work_number} загружена!</b>\n\n"
                    f"📋 <b>Работа пуста.</b>\n\n"
                    f"💬 <b>Опишите задачу:</b>\n"
                    f"• Материал (сталь, алюминий, титан...)\n"
                    f"• Диаметры (с Ø100 до Ø90)\n"
                    f"• Тип обработки (черновая, чистовая)\n"
                    f"• Станок (если известен)\n\n"
                    f"<i>Или нажмите кнопку ниже чтобы начать.</i>",
                    reply_markup=keyboard
                )
        else:
            await callback.message.answer(f"❌ Работа {work_number} не найдена.")
    else:
        await callback.message.answer("❌ Сервис работ недоступен.")


@dp.callback_query(F.data.startswith("delete_work_"))
async def handle_delete_work(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления работы."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    work_number = callback.data.replace("delete_work_", "")
    
    # Показываем подтверждение удаления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{work_number}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"work_menu_{work_number}")
        ]
    ])
    
    await callback.message.answer(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить работу <b>{work_number}</b>?\n\n"
        f"<i>Это действие нельзя отменить.</i>",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("confirm_delete_"))
async def handle_confirm_delete_work(callback: CallbackQuery, state: FSMContext):
    """Удалить работу после подтверждения."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    work_number = callback.data.replace("confirm_delete_", "")
    
    if handler and handler.work_manager:
        if handler.work_manager.delete_work(user_id, work_number):
            await callback.message.answer(f"✅ <b>Работа {work_number} удалена.</b>")
            # Показываем обновленный список работ
            await handle_list_works(callback, state)
        else:
            await callback.message.answer(f"❌ <b>Работа {work_number} не найдена.</b>", reply_markup=create_main_nav_keyboard())
    else:
        await callback.message.answer("❌ Сервис работ недоступен.", reply_markup=create_main_nav_keyboard())


@dp.callback_query(F.data.startswith("save_work_update_"))
async def handle_save_work_update(callback: CallbackQuery, state: FSMContext):
    """Сохранить изменения в существующую работу."""
    await callback.answer("Сохраняю изменения...")
    user_id = str(callback.from_user.id)
    work_number = callback.data.replace("save_work_update_", "")
    
    # Получаем текущий контекст
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    
    if not context:
        await callback.message.answer("❌ Контекст не найден.", reply_markup=create_main_nav_keyboard())
        return
    
    if handler and handler.work_manager:
        # Обновляем работу с текущим контекстом
        if handler.work_manager.update_work(user_id, work_number, context=context):
            await callback.message.answer(
                f"✅ <b>Изменения в работе {work_number} сохранены!</b>\n\n"
                f"💡 Используйте <code>работа {work_number}</code> или кнопку «Мои работы».",
                reply_markup=create_main_nav_keyboard()
            )
        else:
            await callback.message.answer(f"❌ Не удалось сохранить изменения в работу {work_number}.")
    else:
        await callback.message.answer("❌ Сервис работ недоступен.")


def _collect_my_tools_from_context(context: Optional[Context]) -> list:
    """Собрать уникальные инструменты из истории диалога (события tool_saved)."""
    if not context or not context.dialog_history:
        return []
    seen = set()
    tools = []
    for event in context.dialog_history:
        if event.get('event') == 'tool_saved':
            name = (event.get('data') or {}).get('tool_name', '').strip()
            if name and name not in seen:
                seen.add(name)
                tools.append(name)
    return tools


@dp.callback_query(F.data == "list_tools")
async def handle_list_tools(callback: CallbackQuery, state: FSMContext):
    """Показать список инструментов пользователя из истории диалога."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    if context_repository:
        context = context_repository.get_context(user_id)
    else:
        context = user_contexts.get(user_id)
    tools = _collect_my_tools_from_context(context)
    if tools:
        response_lines = ["🔧 <b>Ваши инструменты (из истории диалога):</b>\n"]
        for i, name in enumerate(tools, 1):
            response_lines.append(f"• {name}")
        response_lines.append("\n💡 <i>Укажите инструмент текстом или отправьте фото, чтобы добавить новый.</i>")
        await callback.message.answer("\n".join(response_lines), reply_markup=create_main_nav_keyboard(lang=get_lang(context)))
    else:
        await callback.message.answer(
            "🔧 <b>В истории пока нет сохранённых инструментов.</b>\n\n"
            "💡 Отправьте фото инструмента или опишите его текстом (например: CNMG 120408, фреза 10 мм) — я запомню.",
            reply_markup=create_main_nav_keyboard(lang=get_lang(context))
        )


@dp.callback_query(F.data == "list_works")
async def handle_list_works(callback: CallbackQuery, state: FSMContext):
    """Показать список работ с кнопками действий."""
    await callback.answer()
    user_id = str(callback.from_user.id)
    
    # Показываем список работ
    if handler and handler.work_manager:
        works = handler.work_manager.list_works(user_id, limit=20)
        
        if works:
            response_lines = ["📋 <b>Ваши сохраненные работы:</b>\n"]
            keyboard_buttons = []
            
            for work in works:
                work_num = work.get('work_number', 'unknown')
                desc = work.get('description', '')
                created = work.get('created_at', '')
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        date_str = dt.strftime('%d.%m.%Y %H:%M')
                    except:
                        date_str = created[:10]
                else:
                    date_str = "неизвестно"
                response_lines.append(f"• <b>{work_num}</b> - {desc or 'Без описания'} (от {date_str})")
                
                # Добавляем кнопки для каждой работы
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"📝 {work_num}",
                        callback_data=f"work_menu_{work_num}"
                    )
                ])
            
            response_lines.append("\n💡 Нажмите на кнопку с номером работы для управления.")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await callback.message.answer("\n".join(response_lines), reply_markup=keyboard)
        else:
            await callback.message.answer(
                "📋 <b>Сохраненных работ пока нет.</b>\n\n"
                "💡 Используйте команду <code>сохранить работу</code> чтобы сохранить текущую задачу."
            )
    else:
        await callback.message.answer("❌ Сервис работ недоступен.")


# ============================================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОБРАБОТКИ РЕЗУЛЬТАТОВ HANDLER
# ============================================================================

async def process_handler_result(result: Dict[str, Any], message: types.Message, context: Context, user_id: str):
    """Обработать результат handler и отправить ответ пользователю."""
    action = result.get('action', 'unknown')
    mode = result.get('mode', 'chat')
    
    # Определяем, является ли устройство мобильным (если доступна информация)
    user_agent = None  # Telegram не предоставляет user-agent напрямую
    is_mobile_device = False  # Можно расширить если будет доступна информация
    
    # Обрабатываем результат так же, как в handle_message
    # Для упрощения, здесь можно вызвать соответствующую логику
    
    if action == 'clarify':
        missing = result.get('missing_fields', [])
        keyboard = create_clarify_keyboard(missing, context)
        handler_message = result.get('message', '')
        if handler_message:
            # Адаптируем под устройство
            handler_message = format_for_device(handler_message, is_mobile_device)
            # Разбиваем длинные сообщения
            message_parts = split_long_message(handler_message)
            for i, part in enumerate(message_parts):
                # Клавиатуру добавляем только к последней части
                reply_markup = keyboard if i == len(message_parts) - 1 else None
                await message.answer(part, reply_markup=reply_markup)
        save_context_safe(context, user_id)
    elif action == 'calculate':
        recommendation = result.get('recommendation', {})
        summary = format_context_summary(context)
        if summary and summary != "Пока нет данных...":
            summary = format_for_device(summary, is_mobile_device)
            summary_parts = split_long_message(summary)
            for part in summary_parts:
                await message.answer(part)
        
        rec_text = format_recommendation(recommendation, context)
        rec_text = format_for_device(rec_text, is_mobile_device)
        keyboard = create_after_calculation_keyboard(lang=get_lang(context))
        
        # Разбиваем длинные сообщения
        rec_parts = split_long_message(rec_text)
        for i, part in enumerate(rec_parts):
            # Клавиатуру добавляем только к последней части
            reply_markup = keyboard if i == len(rec_parts) - 1 else None
            await message.answer(part, reply_markup=reply_markup)
        
        save_context_safe(context, user_id)
    elif action == 'tech_process':
        tech_message = result.get('message', '')
        if tech_message:
            tech_message = format_for_device(tech_message, is_mobile_device)
            tech_parts = split_long_message(tech_message)
            for part in tech_parts:
                await message.answer(part)
        save_context_safe(context, user_id)
    elif action == 'collecting_params':
        collecting_message = result.get('message', '')
        if collecting_message:
            collecting_message = format_for_device(collecting_message, is_mobile_device)
            collecting_parts = split_long_message(collecting_message)
            for part in collecting_parts:
                await message.answer(part)
        save_context_safe(context, user_id)
    elif action == 'standard_not_found':
        standard_message = result.get('message', '')
        if standard_message:
            standard_message = format_for_device(standard_message, is_mobile_device)
            standard_parts = split_long_message(standard_message)
            for part in standard_parts:
                await message.answer(part)
        save_context_safe(context, user_id)
    elif action == 'error':
        error_msg = result.get('message', 'Произошла ошибка')
        error_msg = format_for_device(error_msg, is_mobile_device)
        error_parts = split_long_message(error_msg)
        for i, part in enumerate(error_parts):
            reply_markup = create_main_nav_keyboard() if i == len(error_parts) - 1 else None
            await message.answer(part, reply_markup=reply_markup)
        save_context_safe(context, user_id)
    elif action in ('noise', 'noise_fallback', 'internet_search_result', 'standard_search_result'):
        handler_message = result.get('message', '')
        if handler_message:
            handler_message = format_for_device(handler_message, is_mobile_device)
            handler_parts = split_long_message(handler_message)
            for i, part in enumerate(handler_parts):
                reply_markup = create_main_nav_keyboard() if i == len(handler_parts) - 1 else None
                await message.answer(part, reply_markup=reply_markup)
        save_context_safe(context, user_id)
    else:
        # Неизвестное действие - отправляем сообщение из handler если есть
        handler_message = result.get('message', '')
        if handler_message:
            handler_message = format_for_device(handler_message, is_mobile_device)
            handler_parts = split_long_message(handler_message)
            for i, part in enumerate(handler_parts):
                reply_markup = create_main_nav_keyboard() if i == len(handler_parts) - 1 else None
                await message.answer(part, reply_markup=reply_markup)
        else:
            await message.answer(
                "🤔 <b>Не совсем понял.</b>\n\n"
                "💬 <i>Опишите задачу подробнее, например:</i>\n"
                "<code>\"Сталь, токарный ЧПУ, снять с Ø100 до Ø90, черновая обработка\"</code>",
                reply_markup=create_main_nav_keyboard()
            )
        save_context_safe(context, user_id)


@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    """Главный обработчик всех текстовых сообщений."""
    import time
    start_time = time.time()
    
    user_id = str(message.from_user.id)
    user_text = (message.text or "").strip()
    user_name = message.from_user.first_name or "друг"
    
    # Rate limiting
    # Rate limiting (используем async версию если доступна, иначе sync)
    if rate_limiter:
        if inspect.iscoroutinefunction(rate_limiter.is_allowed):
            is_allowed = await rate_limiter.is_allowed(user_id)
        else:
            is_allowed = rate_limiter.is_allowed_sync(user_id)
        
        if not is_allowed:
            if inspect.iscoroutinefunction(rate_limiter.get_remaining_time):
                remaining_time = await rate_limiter.get_remaining_time(user_id)
            else:
                remaining_time = rate_limiter.get_remaining_time_sync(user_id)
            
            await message.answer(
                f"⏳ <b>Слишком много сообщений</b>\n\n"
                f"Пожалуйста, подождите {int(remaining_time)} секунд перед отправкой следующего сообщения."
            )
            return
    
    # Обновляем метрики
    metrics.total_messages += 1
    
    # Проверяем, не переименовываем ли мы работу
    state_data = await state.get_data()
    renaming_work = state_data.get('renaming_work')
    
    if renaming_work and user_text.lower() not in ['отмена', 'cancel', 'отменить']:
        # Обрабатываем как новое имя работы
        if handler and handler.work_manager:
            if handler.work_manager.update_work(user_id, renaming_work, description=user_text):
                await message.answer(
                    f"✅ <b>Работа {renaming_work} переименована!</b>\n\n"
                    f"📝 <b>Новое имя:</b> {user_text}"
                )
                # Очищаем состояние
                await state.update_data(renaming_work=None)
            else:
                await message.answer(f"❌ Не удалось переименовать работу {renaming_work}.")
        else:
            await message.answer("❌ Сервис работ недоступен.")
        return
    
    if renaming_work and user_text.lower() in ['отмена', 'cancel', 'отменить']:
        # Отменяем переименование
        await state.update_data(renaming_work=None)
        await message.answer("❌ Переименование отменено.")
        return
    
    # Проверяем на приветствие
    greetings = ['привет', 'здравствуй', 'здравствуйте', 'добрый день', 'добрый вечер', 
                 'доброе утро', 'hi', 'hello', 'hey', 'салют', 'здарова']
    
    is_greeting = any(greeting in user_text.lower() for greeting in greetings)
    
    # Получаем или создаем контекст (приоритет: context_manager > file_storage > context_repository > user_contexts)
    context = None
    
    if context_manager:
        context = context_manager.get(user_id)
    
    if not context and file_storage:
        context = file_storage.get(user_id)
        # Если загрузили из файла, сохраняем в context_manager
        if context and context_manager:
            context_manager.set(user_id, context)
    
    if not context and context_repository:
        context = context_repository.get_context(user_id)
        # Если загрузили из репозитория, сохраняем в context_manager
        if context and context_manager:
            context_manager.set(user_id, context)
    
    if not context:
        # Fallback на старый способ (в памяти)
        if context_manager:
            context = context_manager.get(user_id)
        if not context:
            context = user_contexts.get(user_id)
    
    if not context:
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Убеждаемся что user_id установлен
    ensure_context_user_id(context, user_id)
    
    # Проверяем, если это первый ответ после приветствия и станок не указан
    # В этом случае текст может быть ответом на вопрос о станке
    # ВАЖНО: Проверяем ПОСЛЕ получения контекста
    # КРИТИЧНО: ГОСТ/ОСТ/DIN/ISO - это СТАНДАРТЫ, НИКОГДА не обрабатываем как станок
    has_standard_keyword = bool(re.search(r'\b(гост|ост|din|iso)\b', user_text.lower()))
    is_first_message = not context.machine_type and not context.dialog_history
    could_be_machine_answer = (
        is_first_message and 
        not is_greeting and 
        len(user_text.strip()) > 2 and
        not has_standard_keyword  # Никогда не принимаем стандарты за станки
    )
    
    # Проверяем запросы на историю и работы (до обработки через handler)
    user_text_lower = user_text.lower().strip()
    
    # Запросы на показ "мои инструменты"
    tools_queries = ['мои инструменты', 'инструменты', 'список инструментов', 'my tools', 'list tools']
    if any(q in user_text_lower for q in tools_queries):
        tools = _collect_my_tools_from_context(context)
        if tools:
            response_lines = ["🔧 <b>Ваши инструменты (из истории диалога):</b>\n"]
            for name in tools:
                response_lines.append(f"• {name}")
            response_lines.append("\n💡 <i>Укажите инструмент текстом или отправьте фото, чтобы добавить новый.</i>")
            await message.answer("\n".join(response_lines), reply_markup=create_main_nav_keyboard(lang=get_lang(context)))
        else:
            await message.answer(
                "🔧 <b>В истории пока нет сохранённых инструментов.</b>\n\n"
                "💡 Отправьте фото инструмента или опишите его текстом (например: CNMG 120408, фреза 10 мм) — я запомню.",
                reply_markup=create_main_nav_keyboard(lang=get_lang(context))
            )
        return
    
    # Запросы на показ истории/работ
    history_queries = ['история', 'историю', 'покажи историю', 'мои работы', 'работы', 
                       'список работ', 'покажи работы', 'show history', 'my works', 'list works']
    
    if any(query in user_text_lower for query in history_queries):
        # Показываем историю диалога и сохраненные работы
        response_lines = []
        
        # История диалога
        if context.dialog_history:
            response_lines.append("📜 <b>История нашего диалога:</b>")
            response_lines.append("")
            
            # Показываем последние 5 событий
            recent_history = context.dialog_history[-5:]
            for i, event in enumerate(recent_history, 1):
                event_type = event.get('event', 'unknown')
                event_data = event.get('data', {})
                timestamp = event.get('timestamp', '')
                
                if event_type == 'message':
                    text = event_data.get('text', '')[:50]
                    if text:
                        response_lines.append(f"{i}. 💬 Сообщение: {text}...")
                elif event_type == 'calculation':
                    response_lines.append(f"{i}. 🧮 Выполнен расчет режимов")
                elif event_type == 'machine_saved':
                    response_lines.append(f"{i}. 🏭 Сохранен станок: {event_data.get('machine_name', '')}")
                elif event_type == 'material_saved':
                    response_lines.append(f"{i}. 🔩 Сохранен материал: {event_data.get('material_name', '')}")
                elif event_type == 'tool_saved':
                    response_lines.append(f"{i}. 🔧 Сохранен инструмент: {event_data.get('tool_name', '')}")
            
            if len(context.dialog_history) > 5:
                response_lines.append(f"\n<i>... и ещё {len(context.dialog_history) - 5} событий</i>")
        else:
            response_lines.append("📜 <b>История диалога пуста.</b>")
        
        # Сохраненные работы
        if handler and handler.work_manager:
            works = handler.work_manager.list_works(user_id, limit=10)
            if works:
                response_lines.append("")
                response_lines.append("📋 <b>Ваши сохраненные работы:</b>")
                response_lines.append("")
                for work in works:
                    desc = work.get('description', 'Без описания')
                    if len(desc) > 50:
                        desc = desc[:50] + "..."
                    response_lines.append(f"• <code>{work['work_number']}</code> - {desc}")
                response_lines.append("")
                response_lines.append("💡 <i>Напиши \"работа W001\" чтобы загрузить работу.</i>")
            else:
                response_lines.append("")
                response_lines.append("📋 <b>У вас пока нет сохранённых работ.</b>")
                response_lines.append("💡 <i>Скажи \"сохранить работу\" чтобы сохранить текущую задачу.</i>")
        
        # Текущий контекст
        has_current_context = (
            context.material or
            context.machine_type or
            context.tool_name or
            context.diameter_start
        )
        
        if has_current_context:
            response_lines.append("")
            response_lines.append("📌 <b>Текущий контекст:</b>")
            if context.machine_type:
                response_lines.append(f"🏭 Станок: {context.machine_type}")
            if context.material:
                response_lines.append(f"🔩 Материал: {context.material}")
            tool_str = _format_tool_display(context)
            if tool_str:
                response_lines.append(f"🔧 Инструмент: {tool_str}")
            if context.diameter_start and context.diameter_end:
                response_lines.append(f"📏 Диаметры: Ø{context.diameter_start} → Ø{context.diameter_end} мм")
        
        await message.answer("\n".join(response_lines))
        return
    
    # Если это приветствие - отвечаем дружелюбно
    # НО: НЕ здороваемся если есть активная задача (стандарт задан, операции заданы, идет сбор параметров)
    if is_greeting:
        # Проверяем есть ли активная задача
        has_active_task = (
            context.standard_id or  # Стандарт задан
            context.part_type or  # Тип детали известен
            context.collecting_params or  # Идет сбор параметров
            context.operation  # Операции заданы (технологический маршрут)
        )
        
        # Если есть активная задача - НЕ здороваемся, продолжаем работу
        if has_active_task:
            # Пропускаем приветствие и продолжаем обработку как обычное сообщение
            is_greeting = False
        else:
            # Нет активной задачи - можно поздороваться
            has_history = (
                context.dialog_history or
                context.material or
                context.machine_type or
                context.tool_name
            )
        
            if has_history:
                greeting_response = (
                    f"👋 <b>Привет, {user_name}!</b>\n\n"
                    f"Рад снова тебя видеть!\n\n"
                )
                
                # Показываем что помним
                if context.machine_type:
                    greeting_response += f"🏭 Помню, ты работаешь на <b>{context.machine_type}</b>\n"
                if context.material:
                    greeting_response += f"🔩 Последний материал: <b>{context.material}</b>\n"
                tool_str = _format_tool_display(context)
                if tool_str:
                    greeting_response += f"🔧 Инструмент: <b>{tool_str}</b>\n"
                
                greeting_response += (
                    "\n💬 <b>Чем могу помочь?</b>\n\n"
                    "• Опиши новую задачу обработки\n"
                    "• Добавить/изменить инструмент\n"
                    "• Изменить параметры станка\n"
                    "• <code>история</code> - показать историю диалога и работы\n"
                    "• <code>мои работы</code> - список сохранённых работ\n"
                    "• Или просто опиши что нужно обработать"
                )
            else:
                # Нет истории - проверяем, есть ли информация о станке и инструменте
                has_machine = context.machine_type
                has_tool = context.tool_name
                
                greeting_response = (
                    f"👋 <b>Привет, {user_name}!</b>\n\n"
                    f"Я <b>CNC Assistant</b> — помощник по режимам резания для токарки и фрезеровки.\n\n"
                    f"📋 <b>Что умею:</b>\n"
                    f"• Подбирать обороты, подачи, глубины резания\n"
                    f"• Работать по ГОСТ/ОСТ (болты, гайки и т.п.)\n"
                    f"• Распознавать технологический маршрут (расточка, сверление, фрезер)\n"
                    f"• Сохранять работы и загружать по номеру\n"
                    f"• Искать информацию в интернете, если чего-то не знаю\n\n"
                )
                
                if not has_machine or not has_tool:
                    # Предлагаем собрать информацию
                    greeting_response += (
                        f"💡 <b>Давайте соберём полную информацию о вас:</b>\n\n"
                    )
                    
                    missing_items = []
                    if not has_machine:
                        missing_items.append("станок")
                    if not has_tool:
                        missing_items.append("инструмент")
                    
                    if missing_items:
                        greeting_response += f"📝 <b>Нужно указать:</b> {', '.join(missing_items)}\n\n"
                    
                    greeting_response += (
                        f"🔧 <b>Команды:</b> <code>помощь</code> · <code>мои работы</code> · <code>история</code>\n\n"
                        f"<i>Используйте кнопки ниже или просто напишите информацию.</i>"
                    )
                    
                    # Создаем клавиатуру для сбора информации
                    buttons = []
                    if not has_machine:
                        buttons.append([InlineKeyboardButton(text="🏭 Указать станок", callback_data="select_machine")])
                    if not has_tool:
                        buttons.append([InlineKeyboardButton(text="🔧 Указать инструмент", callback_data="select_tool")])
                    
                    if buttons:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                        await message.answer(greeting_response, reply_markup=keyboard)
                    else:
                        await message.answer(greeting_response)
                else:
                    # Вся информация есть - стандартное приветствие
                    greeting_response += (
                        f"💬 <b>Что написать:</b>\n"
                        f"• Задача: <code>сталь Ø100→90 черновая</code>, <code>титан с Ø200 до Ø50</code>\n"
                        f"• Стандарт: <code>добавим ОСТ 33057-80</code>, <code>ГОСТ 7798</code>\n"
                        f"• Или отправь фото инструмента\n\n"
                        f"🔧 <b>Команды:</b> <code>помощь</code> · <code>мои работы</code> · <code>история</code>\n\n"
                        f"<i>Просто напиши что нужно — я пойму.</i>"
                    )
                    await message.answer(greeting_response)
            
            save_context_safe(context, user_id)
            return
    
    # Если ожидаем подтверждение поиска стандарта — сразу в handler, не обрабатывать как станок
    if context.pending_standard_search and handler:
        # Пропускаем could_be_machine и идём в handler
        pass
    # Ответ с уточнением по станку: мощность и/или обороты (станок уже указан)
    elif context.machine_type and not context.machine_power and handler:
        parsed_data = handler.parser.parse(user_text)
        # Считаем сообщение уточнением по станку только если нет полной задачи (материал+диаметры)
        is_likely_specs = parsed_data and (
            parsed_data.machine_power is not None or getattr(parsed_data, "rpm", None) is not None
        ) and not (parsed_data.material and parsed_data.diameter_start and parsed_data.diameter_end)
        if is_likely_specs:
            from app.core.context import DataSource
            power = parsed_data.machine_power
            rpm = getattr(parsed_data, "rpm", None)
            if power is not None:
                context.set_field("machine_power", power, DataSource.USER, confidence=1.0, reasoning="Указано пользователем")
            if rpm is not None:
                context.set_field("machine_max_rpm", rpm, DataSource.USER, confidence=1.0, reasoning="Указано пользователем")
            if handler.machine_saver:
                handler.machine_saver.update_machine_params(
                    context.machine_type,
                    power_kw=power,
                    max_rpm=rpm,
                )
            save_context_safe(context, user_id)
            p_str = f" {power} кВт" if power is not None else ""
            r_str = f" {rpm} об/мин" if rpm is not None else ""
            await message.answer(
                f"✅ Записал:{p_str}{r_str}. Подбор режимов будет точнее.\n\n💬 Опишите задачу обработки или укажите инструмент.",
                reply_markup=create_post_machine_keyboard()
            )
            return
    # Если это первый ответ после приветствия и похоже на название станка - обрабатываем как станок
    elif could_be_machine_answer and not is_greeting and handler:
        # Парсим текст для поиска станка
        parsed_data = handler.parser.parse(user_text)
        if parsed_data and parsed_data.machine_type:
            # Нашли станок - сохраняем и подтверждаем
            from app.core.context import DataSource
            context.set_field(
                'machine_type',
                parsed_data.machine_type,
                DataSource.USER,
                confidence=1.0,
                reasoning="Указан пользователем при первом обращении"
            )
            if parsed_data.machine_power is not None:
                context.set_field("machine_power", parsed_data.machine_power, DataSource.USER, confidence=1.0, reasoning="Указано в сообщении")
            if getattr(parsed_data, "rpm", None) is not None:
                context.set_field("machine_max_rpm", parsed_data.rpm, DataSource.USER, confidence=1.0, reasoning="Указано в сообщении")
            
            # Сохраняем станок если он неизвестен
            if handler and handler.machine_saver:
                machine_info = handler.knowledge_service.find_machine(parsed_data.machine_type)
                if not machine_info:
                    known_types = ['токарный чпу', 'токарный ручной', 'фрезерный чпу', 'фрезерный ручной']
                    if parsed_data.machine_type.lower() not in known_types:
                        machine_id = handler.machine_saver.save_unknown_machine(
                            machine_name=parsed_data.machine_type,
                            machine_type=None,
                            power_kw=parsed_data.machine_power,
                            max_rpm=getattr(parsed_data, "rpm", None),
                        )
                        if machine_id and handler.internet_search:
                            # Пробуем найти информацию в интернете
                            try:
                                search_result = await handler.internet_search.search_and_save_machine(
                                    parsed_data.machine_type
                                )
                                if search_result.get('success'):
                                    data = search_result.get('data', {})
                                    if data.get('power') is not None:
                                        context.set_field("machine_power", float(data['power']), DataSource.USER, confidence=0.9, reasoning="Найдено в интернете")
                                    if data.get('max_rpm') is not None:
                                        context.set_field("machine_max_rpm", float(data['max_rpm']), DataSource.USER, confidence=0.9, reasoning="Найдено в интернете")
                                    await message.answer(
                                        f"✅ <b>Отлично! Станок {parsed_data.machine_type} сохранён.</b>\n\n"
                                        f"🔍 Нашёл информацию в интернете:\n"
                                        f"• Мощность: {data.get('power', 'не указана')} кВт\n"
                                        f"• Макс. обороты: {data.get('max_rpm', 'не указаны')} об/мин\n\n"
                                        f"💬 Теперь опиши задачу обработки!",
                                        reply_markup=create_post_machine_keyboard()
                                    )
                                else:
                                    await message.answer(
                                        f"✅ <b>Станок {parsed_data.machine_type} сохранён.</b>\n\n"
                                        f"💬 Теперь опиши задачу обработки!",
                                        reply_markup=create_post_machine_keyboard()
                                    )
                            except Exception as e:
                                logger.debug(f"Internet search failed: {e}")
                                await message.answer(
                                    f"✅ <b>Станок {parsed_data.machine_type} сохранён.</b>\n\n"
                                    f"💬 Теперь опиши задачу обработки!",
                                    reply_markup=create_post_machine_keyboard()
                                )
                            # Если не нашли в интернете и пользователь не указал мощность/обороты — спросим
                            if not context.machine_power and not context.machine_max_rpm:
                                await message.answer(
                                    "💡 <b>Если знаете</b> — укажите мощность шпинделя (кВт) и макс. обороты (об/мин). "
                                    "Например: <code>15 кВт 3000 об/мин</code> — подбор режимов будет точнее."
                                )
                            save_context_safe(context, user_id)
                            return
                        else:
                            # Сохранён без поиска в интернете
                            await message.answer(
                                f"✅ <b>Станок {parsed_data.machine_type} сохранён.</b>\n\n💬 Теперь опиши задачу или укажи инструмент.",
                                reply_markup=create_post_machine_keyboard()
                            )
                            if not context.machine_power and not context.machine_max_rpm:
                                await message.answer("💡 Если знаете — напишите мощность (кВт) и макс. обороты (об/мин). Например: 15 кВт 3000 об/мин")
                            save_context_safe(context, user_id)
                            return
            
            # Если станок известен или просто тип
            await message.answer(
                f"✅ <b>Понял, работаешь на {parsed_data.machine_type}.</b>\n\n"
                f"💬 Теперь опиши задачу обработки!",
                reply_markup=create_post_machine_keyboard()
            )
            if not context.machine_power and not context.machine_max_rpm:
                machine_info_ctx = handler.knowledge_service.find_machine(parsed_data.machine_type) if handler else None
                if not (machine_info_ctx and (getattr(machine_info_ctx, "power_kw", None) or getattr(machine_info_ctx, "max_rpm", None))):
                    await message.answer("💡 Если знаете — укажите мощность (кВт) и макс. обороты (об/мин). Например: 15 кВт 3000 об/мин")
            save_context_safe(context, user_id)
            return
    
    try:
        if not handler:
            await message.answer(
                "❌ Бот не инициализирован. Перезапустите бота."
            )
            return

        # Если уже была рекомендация — ответ с числами/режимами считаем отзывом оператора (не передаём в handler как "шум")
        if context.recommended_vc and _looks_like_experience_feedback(user_text):
            await handle_user_experience(message, context, user_text)
            save_context_safe(context, user_id)
            return

        # Ожидаем ответ "номер работы" или "Новая" после предложения применить стандарт
        if context.pending_standard_apply and handler:
            low = user_text.strip().lower()
            is_new = low in ("новая", "new", "создать", "новая работа", "новая задача")
            work_number = _extract_work_number(user_text) if not is_new else None
            if is_new or work_number:
                standard_id = context.pending_standard_apply
                context.pending_standard_apply = None
                parts = standard_id.split("_", 1)
                stype, snum = (parts[0], parts[1]) if len(parts) == 2 else (standard_id, "")
                try:
                    standard_info = handler.standard_service.get_standard_info(stype, snum)
                except Exception:
                    standard_info = {}
                if is_new:
                    context = Context(user_id=user_id, session_id=context.session_id, lang=context.lang)
                    context.standard_id = standard_id
                elif work_number:
                    loaded_context = handler.work_manager.load_work_to_context(user_id, work_number)
                    if loaded_context:
                        context = loaded_context
                    context.standard_id = standard_id
                if standard_info:
                    template = standard_info.get("template", {})
                    std_data = standard_info.get("standard_data") or {}
                    if not context.material and (std_data or template.get("default_material")):
                        context.material = (
                            (handler.standard_service.get_materials(std_data) or [None])[0]
                            if std_data else template.get("default_material")
                        ) or context.material
                save_context_safe(context, user_id)
                if is_new:
                    await message.answer(
                        f"✅ <b>Создана новая задача с параметрами стандарта {standard_id.replace('_', ' ')}.</b>\n\n"
                        f"💬 Укажи диаметр/длину при необходимости или напиши <b>давай</b> для расчёта режимов.",
                        reply_markup=create_main_nav_keyboard(lang=get_lang(context)),
                    )
                else:
                    summary = format_context_summary(context)
                    await message.answer(
                        f"✅ <b>Параметры стандарта применены к работе {work_number}.</b>\n\n{summary}\n\n"
                        f"💬 Напиши <b>давай</b> для расчёта режимов.",
                        reply_markup=create_continue_keyboard(lang=get_lang(context)),
                    )
                return
            else:
                await message.answer(
                    "💬 Укажи <b>номер работы</b> (1, W001) или напиши <b>Новая</b> — создать новую задачу с параметрами стандарта."
                )
                save_context_safe(context, user_id)
                return

        # Обрабатываем сообщение через handler
        result = await handler.process_message(
            user_text=user_text,
            user_id=user_id,
            session_id=context.session_id,
            existing_context=context
        )
        
        # Handler обновляет существующий контекст, но нужно убедиться что он сохранен
        # Получаем обновленный контекст из handler (он модифицирует existing_context)
        # Сохраняем контекст после обработки (с проверкой user_id)
        save_context_safe(context, user_id)
        
        # Определяем действие
        action = result.get('action', 'unknown')
        is_command = result.get('is_command', False)
        mode = result.get('mode', 'unknown')
        
        # ПРИОРИТЕТ 1: PROJECT MODE (работа по ГОСТ/чертежу или технологический маршрут)
        if mode == 'project' or action in ['project_mode', 'standard_part', 'standard_part_unknown', 'tech_process', 'collecting_params', 'standard_not_found', 'standard_search_result']:
            project_message = result.get('message', '')
            if result.get('offer_apply_to_work') and result.get('standard_id'):
                context.pending_standard_apply = result.get('standard_id')
                project_message = (project_message or '') + (
                    "\n\n💬 <b>Применить к текущей работе или создать новую?</b> "
                    "Укажи номер работы (1, W001) или напиши «Новая»."
                )
            if project_message:
                await message.answer(project_message)
            save_context_safe(context, user_id)
            return
        
        # ПРИОРИТЕТ 2: Команды работы с работами (work_load, work_delete)
        if action == 'work_load' and handler and handler.work_manager:
            work_number = _extract_work_number(user_text)
            if work_number:
                loaded_context = handler.work_manager.load_work_to_context(user_id, work_number)
                if loaded_context:
                    context = loaded_context
                    save_context_safe(context, user_id)
                    summary = format_context_summary(context)
                    has_data = bool(
                        context.material or
                        context.diameter_start or
                        context.diameter_end or
                        context.operation or
                        context.standard_id
                    )
                    keyboard = create_continue_keyboard(lang=get_lang(context))
                    if has_data and (context.diameter_start or context.diameter_end) and context.material:
                        result = await handler.process_message(
                            user_text="давай",
                            user_id=user_id,
                            session_id=context.session_id,
                            existing_context=context,
                        )
                        if result.get("action") == "calculate" and result.get("recommendation"):
                            save_context_safe(context, user_id)
                            rec_text = format_recommendation(result["recommendation"], context)
                            await message.answer(
                                f"✅ <b>Работа {work_number} загружена!</b>\n\n{summary}\n",
                                reply_markup=keyboard,
                            )
                            await message.answer(
                                rec_text,
                                reply_markup=create_after_calculation_keyboard(lang=get_lang(context)),
                            )
                        else:
                            await message.answer(
                                f"✅ <b>Работа {work_number} загружена!</b>\n\n"
                                f"{summary}\n\n"
                                f"💬 <i>Можете продолжить или описать что нужно сделать.</i>",
                                reply_markup=keyboard,
                            )
                    elif has_data:
                        await message.answer(
                            f"✅ <b>Работа {work_number} загружена!</b>\n\n"
                            f"{summary}\n\n"
                            f"💬 <i>Можете продолжить или описать что нужно сделать.</i>",
                            reply_markup=keyboard,
                        )
                    else:
                        await message.answer(
                            f"✅ <b>Работа {work_number} загружена!</b>\n\n"
                            f"📋 <b>Работа пуста.</b>\n\n"
                            f"💬 <b>Опишите задачу:</b>\n"
                            f"• Материал (сталь, алюминий, титан...)\n"
                            f"• Диаметры (с Ø100 до Ø90)\n"
                            f"• Тип обработки (черновая, чистовая)\n"
                            f"• Станок (если известен)\n\n"
                            f"<i>Или нажмите кнопку ниже чтобы начать.</i>",
                            reply_markup=keyboard,
                        )
                else:
                    await message.answer(
                        f"❌ <b>Работа {work_number} не найдена.</b>\n\n"
                        f"💡 <i>Используйте \"мои работы\" чтобы увидеть список.</i>"
                    )
                return
        
        if action == 'work_delete' and handler and handler.work_manager:
            work_number = _extract_work_number(user_text)
            if work_number:
                if handler.work_manager.delete_work(user_id, work_number):
                    await message.answer(f"✅ <b>Работа {work_number} удалена.</b>")
                else:
                    await message.answer(f"❌ <b>Работа {work_number} не найдена.</b>")
                return
        
        if action == 'work_rename' and handler and handler.work_manager:
            params = _extract_work_rename_params(user_text)
            if params:
                work_number, new_name = params
                if handler.work_manager.update_work(user_id, work_number, description=new_name):
                    await message.answer(
                        f"✅ <b>Работа {work_number} переименована.</b>\n\n"
                        f"Новое название: <i>{new_name}</i>"
                    )
                else:
                    await message.answer(f"❌ <b>Работа {work_number} не найдена.</b>")
            else:
                await message.answer(
                    "💡 <b>Как переименовать работу:</b>\n\n"
                    "• <code>переименовать работу W001 в Втулка М12</code>\n"
                    "• <code>назвать работу W001 Черновая сталь</code>\n"
                    "• <code>переименовать W001 в Новое название</code>"
                )
            return
        
        if action == 'tool_name_set':
            nav_kb = create_main_nav_keyboard()
            display_name = _extract_tool_display_name(user_text)
            if display_name and context.tool_name:
                context.tool_display_name = display_name
                save_context_safe(context, user_id)
                await message.answer(
                    f"✅ <b>Инструмент назван:</b> <i>{display_name}</i>\n\n"
                    f"🔧 {display_name} ({context.tool_name})",
                    reply_markup=nav_kb
                )
            elif display_name:
                await message.answer(
                    "❌ <b>Сначала укажите инструмент.</b>\n\n"
                    "Отправьте фото инструмента или напишите его марку (CNMG, WNMG и т.п.), "
                    "затем используйте команду <code>назови инструмент Моё имя</code>.",
                    reply_markup=nav_kb
                )
            else:
                await message.answer(
                    "💡 <b>Как дать имя инструменту:</b>\n\n"
                    "• <code>назови инструмент Мой черновой</code>\n"
                    "• <code>назови этот инструмент Резец для титана</code>\n"
                    "• <code>имя инструмента Втулочный</code>\n\n"
                    "<i>Сначала должен быть указан инструмент (фото или марка).</i>",
                    reply_markup=nav_kb
                )
            return
        
        # ПРИОРИТЕТ 3: Жесткие команды (help, capabilities и т.д.)
        if is_command or action in ['help', 'capabilities', 'works_list', 'tools_list', 'history', 'work_save', 'work_load', 'work_delete', 'work_rename', 'tool_name_set', 'material_equivalent']:
            # Обработка команды поиска эквивалентов материалов
            if action == 'material_equivalent':
                # Извлекаем название материала из текста
                material_name = user_text.replace('эквивалент', '').replace('соответствие', '').replace('маркировка', '').strip()
                
                # Если материал не указан, пытаемся извлечь из контекста
                if not material_name or len(material_name) < 2:
                    if context.material:
                        material_name = context.material
                    else:
                        await message.answer(
                            "📌 <b>Поиск эквивалентов материалов</b>\n\n"
                            "💬 <b>Использование:</b>\n"
                            "• <code>эквивалент Ст45</code>\n"
                            "• <code>соответствие 304</code>\n"
                            "• <code>маркировка 12Х18Н10Т</code>\n\n"
                            "Или укажите материал в задаче.",
                            reply_markup=create_main_nav_keyboard()
                        )
                        return
                
                # Ищем эквиваленты
                if handler and handler.knowledge_service:
                    equivalents_text = handler.knowledge_service.format_material_equivalents(material_name)
                    await message.answer(equivalents_text, reply_markup=create_main_nav_keyboard())
                else:
                    await message.answer("❌ Сервис знаний недоступен.", reply_markup=create_main_nav_keyboard())
                return
            
            if action == 'help':
                help_text = (
                    "📖 <b>Помощь по использованию бота</b>\n\n"
                    "🎯 <b>Основная функция:</b> подбор режимов резания для токарной и фрезерной обработки.\n\n"
                    "📝 <b>Как описать задачу:</b> материал, диаметры (с Ø100 до Ø90), тип обработки, станок, инструмент — в любом порядке.\n\n"
                    "💡 <b>Примеры:</b>\n"
                    "<code>Титан, токарный ЧПУ, снять с Ø200 до Ø50</code>\n"
                    "<code>Сталь 45, черновая, Ø100→90</code>\n\n"
                    "🔧 <b>Команды:</b> <code>история</code>, <code>мои работы</code>, <code>сохранить работу</code>, <code>работа W001</code>, "
                    "<code>назови инструмент ...</code>, <code>эквивалент Ст45</code>, <code>что ты можешь</code>.\n\n"
                    "💬 <i>Просто опиши задачу — я пойму.</i>"
                )
                await message.answer(help_text, reply_markup=create_main_nav_keyboard())
                return
            
            elif action == 'capabilities':
                cap_text = (
                    "🤖 <b>Я инженерный помощник для токарной и фрезерной обработки.</b>\n\n"
                    "💡 <b>Что умею:</b> подбор режимов резания, учёт материала и диаметра, распознавание инструмента по фото, сохранение работ.\n\n"
                    "📝 Опиши задачу в любом порядке или используй кнопки ниже.\n\n"
                    "💬 <i>Хочешь рассчитать режим — просто напиши параметры.</i>"
                )
                await message.answer(cap_text, reply_markup=create_main_nav_keyboard())
                return
            
            # Остальные команды обрабатываются ниже в коде
            # (works_list, history, work_save и т.д. уже обрабатываются)
        
        # Обработка не-инженерных интентов (если не команда)
        if not is_command:
            if action == 'machine_query':
                # Вопрос о станках - показываем список с кнопками
                if handler and handler.knowledge_service:
                    machines = handler.knowledge_service.get_all_machines()
                    if machines:
                        lines = ["🏭 <b>Известные типы станков:</b>\n"]
                        for machine_type, machine_data in machines.items():
                            power = machine_data.power_kw or 'не указана'
                            max_rpm = machine_data.max_rpm or 'не указаны'
                            lines.append(
                                f"• <b>{machine_type}</b>\n"
                                f"  └ Мощность: {power} кВт, Макс. обороты: {max_rpm} об/мин"
                            )
                        lines.append("\n💡 <i>Выберите станок из списка ниже или введите название вручную.</i>")
                        
                        keyboard = create_machine_type_keyboard()
                        await message.answer("\n".join(lines), reply_markup=keyboard)
                    else:
                        keyboard = create_machine_type_keyboard()
                        await message.answer(
                            "🏭 <b>Выберите тип станка:</b>\n\n"
                            "💡 <i>Или введите название станка вручную (например: Gamma 1250, NEF500)</i>",
                            reply_markup=keyboard
                        )
                else:
                    keyboard = create_machine_type_keyboard()
                    await message.answer(
                        "🏭 <b>Выберите тип станка:</b>\n\n"
                        "💡 <i>Или введите название станка вручную (например: Gamma 1250, NEF500)</i>",
                        reply_markup=keyboard
                    )
                return
            
            if action == 'meta_capabilities':
                await message.answer(result.get('message', ''), reply_markup=create_main_nav_keyboard())
                return
            
        if action in ('noise', 'noise_fallback', 'internet_search_result', 'standard_search_result'):
            await message.answer(result.get('message', ''), reply_markup=create_main_nav_keyboard())
            save_context_safe(context, user_id)
            return
        
        if action == 'clarify_intent':
            await message.answer(result.get('message', ''), reply_markup=create_main_nav_keyboard())
            save_context_safe(context, user_id)
            return
        
        if action == 'greeting':
            # Приветствие уже обработано выше
            save_context_safe(context, user_id)
            return
        
        if action == 'clarify':
            # Нужно уточнить данные
            missing = result.get('missing_fields', [])
            
            # Проверяем, есть ли готовое сообщение из handler (например, для загруженной работы)
            handler_message = result.get('message', '')
            is_loaded_work = context.session_id and context.session_id.startswith('work_')
            
            # Если есть сообщение из handler и это загруженная работа - используем его
            if handler_message and is_loaded_work:
                keyboard = create_clarify_keyboard(missing, context)
                await message.answer(handler_message, reply_markup=keyboard)
                save_context_safe(context, user_id)
                return
            
            # Проверяем, были ли сохранены новые сущности
            saved_entities = []
            for history_item in context.dialog_history[-5:]:  # Проверяем последние 5 событий
                if history_item.get('event') == 'machine_saved':
                    saved_entities.append(f"🏭 Станок <b>{history_item.get('data', {}).get('machine_name')}</b> сохранён в базу")
                elif history_item.get('event') == 'material_saved':
                    saved_entities.append(f"🔩 Материал <b>{history_item.get('data', {}).get('material_name')}</b> сохранён в базу")
                elif history_item.get('event') == 'tool_saved':
                    saved_entities.append(f"🔧 Инструмент <b>{history_item.get('data', {}).get('tool_name')}</b> сохранён в базу")
            
            # Проверяем, есть ли уже какая-то информация в контексте
            has_some_info = (
                context.material or
                context.machine_type or
                context.tool_name or
                context.diameter_start or
                context.diameter_end
            )
            
            if has_some_info:
                # Есть какая-то информация - показываем что знаем и что нужно уточнить
                response_lines = []
                
                # Показываем сохраненные сущности если есть
                if saved_entities:
                    response_lines.append("✅ <b>Сохранено в базу знаний:</b>")
                    for entity in saved_entities:
                        response_lines.append(f"• {entity}")
                    response_lines.append("")
                
                response_lines.append("🤔 <b>Нужно уточнить несколько моментов:</b>")
                response_lines.append("")
                
                if 'material' in missing:
                    response_lines.append("• <b>Из какого материала</b> заготовка? (сталь, алюминий, нержавейка...)")
                
                if 'diameter_start' in missing or 'diameter_end' in missing:
                    response_lines.append("• <b>Какие диаметры?</b> (например: с Ø100 до Ø90)")
                
                if 'operation' in missing:
                    response_lines.append("• <b>Какая операция?</b> (черновая, чистовая...)")
                
                # Показываем что уже знаем
                response_lines.append("")
                response_lines.append("<b>Что я уже знаю:</b>")
                
                known_info = format_context_summary(context)
                if known_info and known_info != "Пока нет данных...":
                    response_lines.append(known_info)
                
                response_lines.append("")
                response_lines.append("💬 <i>Можете описать всё в одном сообщении или использовать кнопки ниже.</i>")
                
                response = "\n".join(response_lines)
            else:
                # Нет информации - стандартный запрос
                response_lines = []
                
                # Показываем сохраненные сущности если есть
                if saved_entities:
                    response_lines.append("✅ <b>Сохранено в базу знаний:</b>")
                    for entity in saved_entities:
                        response_lines.append(f"• {entity}")
                    response_lines.append("")
                
                response_lines.append(format_clarification_request(context, missing))
                response = "\n".join(response_lines)
            
            # Добавляем клавиатуру для выбора параметров
            keyboard = create_clarify_keyboard(missing, context)
            await message.answer(response, reply_markup=keyboard)
            
            # Сохраняем контекст после уточнения (с проверкой user_id)
            save_context_safe(context, user_id)
        
        elif action == 'calculate':
            # Можно рассчитать
            recommendation = result.get('recommendation', {})
            metrics.total_calculations += 1
            
            # Показываем что поняли
            summary = format_context_summary(context)
            if summary and summary != "Пока нет данных...":
                summary = format_for_device(summary, False)
                summary_parts = split_long_message(summary)
                for part in summary_parts:
                    await message.answer(part)
            
            # Показываем эквиваленты материала, если материал распознан
            if context.material and handler and handler.knowledge_service:
                material_equiv = handler.knowledge_service.format_material_equivalents(context.material)
                # Проверяем, что эквиваленты найдены (не сообщение об ошибке)
                if "не найден" not in material_equiv and "недоступна" not in material_equiv:
                    material_equiv = format_for_device(material_equiv, False)
                    material_parts = split_long_message(material_equiv)
                    for part in material_parts:
                        await message.answer(part)
            
            # Показываем рекомендацию с кнопками
            rec_text = format_recommendation(recommendation, context)
            # Адаптируем под устройство
            is_mobile_device = False  # Можно расширить если будет доступна информация
            rec_text = format_for_device(rec_text, is_mobile_device)
            keyboard = create_after_calculation_keyboard(lang=get_lang(context))
            
            # Разбиваем длинные сообщения
            rec_parts = split_long_message(rec_text)
            for i, part in enumerate(rec_parts):
                # Клавиатуру добавляем только к последней части
                reply_markup = keyboard if i == len(rec_parts) - 1 else None
                await message.answer(part, reply_markup=reply_markup)
            
            # Сохраняем рекомендацию в контекст
            context.recommended_vc = recommendation.get('vc_m_min') or recommendation.get('vc')
            context.recommended_rpm = recommendation.get('rpm')
            context.recommended_feed = recommendation.get('feed_mm_rev') or recommendation.get('feed')
            context.recommended_ap = recommendation.get('ap_mm') or recommendation.get('ap')
            context.recommended_power = recommendation.get('power_kw')
            
            # Добавляем в историю
            context.add_to_history('recommendation_shown', {
                'recommendation': recommendation
            })
            
            # Сохраняем обновленный контекст (с проверкой user_id)
            save_context_safe(context, user_id)
            
            # Предлагаем сохранить работу
            if handler and handler.work_manager:
                await message.answer(
                    "💾 <b>Хотите сохранить эту работу?</b>\n\n"
                    "Напишите <code>сохранить работу</code> чтобы сохранить задачу под номером.\n"
                    "Потом сможете быстро загрузить её по номеру."
                )
            
            # Сохраняем контекст после расчета (с проверкой user_id)
            save_context_safe(context, user_id)
        
        elif action == 'tech_process':
            # Технологический маршрут распознан
            tech_message = result.get('message', '')
            if tech_message:
                await message.answer(tech_message)
            # Сохраняем контекст после распознавания маршрута
            save_context_safe(context, user_id)
        
        elif action == 'collecting_params':
            # Сбор параметров для стандартной детали или технологического маршрута
            collecting_message = result.get('message', '')
            if collecting_message:
                await message.answer(collecting_message)
            # Сохраняем контекст
            save_context_safe(context, user_id)
        
        elif action == 'standard_not_found':
            # Стандарт не найден в базе
            standard_message = result.get('message', '')
            if standard_message:
                await message.answer(standard_message)
            save_context_safe(context, user_id)
        
        elif action == 'error':
            # Ошибка
            error_msg = result.get('message', 'Произошла ошибка')
            await message.answer(
                f"❌ <b>Ошибка</b>\n\n{error_msg}\n\n"
                f"💡 <i>Попробуйте описать задачу по-другому.</i>"
            )
        
        else:
            # Проверяем команды для работы с работами
            user_text_lower = user_text.lower()
            
            # Команды для работы с работами
            if any(cmd in user_text_lower for cmd in ['сохранить работу', 'сохрани работу', 'сохранить работу', 
                                                       'добавить работу', 'добавь работу', 'save work', 'add work']):
                # Сохранить текущую работу
                if handler and handler.work_manager:
                    work_number = handler.work_manager.create_work(
                        user_id=user_id,
                        description=f"Работа от {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                        context=context
                    )
                    if work_number:
                        await message.answer(
                            f"✅ <b>Работа сохранена!</b>\n\n"
                            f"📋 <b>Номер работы:</b> <code>{work_number}</code>\n\n"
                            f"💡 <i>Используй номер для быстрого доступа к работе.</i>\n\n"
                            f"Команды:\n"
                            f"• <code>мои работы</code> - список всех работ\n"
                            f"• <code>работа {work_number}</code> - загрузить работу\n"
                            f"• <code>удалить {work_number}</code> - удалить работу\n"
                            f"• <code>переименовать работу {work_number} в Название</code> - переименовать"
                        )
                        # Сохраняем контекст после сохранения работы (с проверкой user_id)
                        save_context_safe(context, user_id)
                    else:
                        await message.answer("❌ Не удалось сохранить работу. Попробуйте ещё раз.")
                else:
                    await message.answer("❌ Менеджер работ не доступен.")
            
            elif any(cmd in user_text_lower for cmd in ['мои работы', 'список работ', 'работы', 'покажи работы',
                                                         'my works', 'list works', 'show works']):
                # Показать список работ
                if handler and handler.work_manager:
                    works = handler.work_manager.list_works(user_id, limit=20)
                    if works:
                        response_lines = []
                        response_lines.append("📋 <b>Ваши сохраненные работы:</b>")
                        response_lines.append("")
                        for work in works:
                            desc = work.get('description', 'Без описания')
                            if len(desc) > 60:
                                desc = desc[:60] + "..."
                            created_at = work.get('created_at', '')
                            if created_at:
                                try:
                                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    date_str = dt.strftime('%d.%m.%Y %H:%M')
                                except:
                                    date_str = ''
                            else:
                                date_str = ''
                            
                            if date_str:
                                response_lines.append(
                                    f"• <code>{work['work_number']}</code> - {desc} <i>({date_str})</i>"
                                )
                            else:
                                response_lines.append(
                                    f"• <code>{work['work_number']}</code> - {desc}"
                                )
                        response_lines.append("")
                        response_lines.append("💡 <i>Команды:</i>")
                        response_lines.append(f"• <code>работа {works[0]['work_number']}</code> - загрузить работу")
                        response_lines.append("• <code>сохранить работу</code> - сохранить текущую задачу")
                        response_lines.append("• <code>удалить W001</code> - удалить работу")
                        response_lines.append("• <code>переименовать работу W001 в Название</code> - переименовать работу")
                        await message.answer("\n".join(response_lines))
                    else:
                        await message.answer(
                            "📋 <b>У вас пока нет сохранённых работ.</b>\n\n"
                            "💡 <i>Скажи \"сохранить работу\" чтобы сохранить текущую задачу.</i>"
                        )
                else:
                    await message.answer("❌ Менеджер работ не доступен.")
            
            elif user_text_lower.startswith('работа ') or user_text_lower.startswith('work '):
                # Загрузить работу по номеру
                work_number = user_text.split()[-1].upper().strip()
                if handler and handler.work_manager:
                    loaded_context = handler.work_manager.load_work_to_context(user_id, work_number)
                    if loaded_context:
                        # Обновляем контекст пользователя
                        context = loaded_context  # Используем загруженный контекст
                        # Сохраняем контекст (с проверкой user_id)
                        save_context_safe(context, user_id)
                        
                        summary = format_context_summary(context)
                        await message.answer(
                            f"✅ <b>Работа {work_number} загружена!</b>\n\n"
                            f"{summary}\n\n"
                            f"💬 <i>Можете продолжить работу с этой задачей.</i>"
                        )
                    else:
                        await message.answer(
                            f"❌ <b>Работа {work_number} не найдена.</b>\n\n"
                            f"💡 <i>Используйте \"мои работы\" чтобы увидеть список.</i>"
                        )
                else:
                    await message.answer("❌ Менеджер работ не доступен.")
            
            elif user_text_lower.startswith('удалить ') or user_text_lower.startswith('delete '):
                # Удалить работу
                work_number = user_text.split()[-1].upper().strip()
                if handler and handler.work_manager:
                    if handler.work_manager.delete_work(user_id, work_number):
                        await message.answer(
                            f"✅ <b>Работа {work_number} удалена.</b>"
                        )
                    else:
                        await message.answer(
                            f"❌ <b>Работа {work_number} не найдена.</b>"
                        )
                else:
                    await message.answer("❌ Менеджер работ не доступен.")
            
            elif any(cmd in user_text_lower for cmd in ['что за станок', 'что это за станок', 'расскажи о станке', 'ты меня помнишь', 'помнишь меня']):
                # Информация о станке или проверка памяти
                if 'помнишь' in user_text_lower or 'помнит' in user_text_lower:
                    # Проверка памяти
                    has_memory = (
                        context.machine_type or
                        context.material or
                        context.tool_name or
                        context.diameter_start or
                        context.dialog_history
                    )
                    
                    if has_memory:
                        response_lines = []
                        response_lines.append("✅ <b>Да, помню!</b>\n\n")
                        response_lines.append("<b>Что я знаю о вас:</b>\n")
                        
                        if context.machine_type:
                            response_lines.append(f"🏭 <b>Станок:</b> {context.machine_type}")
                        if context.material:
                            response_lines.append(f"🔩 <b>Материал:</b> {context.material}")
                        tool_str = _format_tool_display(context)
                        if tool_str:
                            response_lines.append(f"🔧 <b>Инструмент:</b> {tool_str}")
                        if context.diameter_start and context.diameter_end:
                            response_lines.append(f"📏 <b>Диаметры:</b> Ø{context.diameter_start} → Ø{context.diameter_end} мм")
                        
                        if context.dialog_history:
                            response_lines.append(f"\n💬 <b>История диалога:</b> {len(context.dialog_history)} сообщений")
                        
                        response_lines.append("\n💡 <i>Могу продолжить работу с этими данными.</i>")
                        await message.answer("\n".join(response_lines))
                    else:
                        await message.answer(
                            "🤔 <b>Пока мало информации.</b>\n\n"
                            "Расскажите о себе:\n"
                            "• На каком станке работаете\n"
                            "• С какими материалами работаете\n"
                            "• Какие инструменты используете\n\n"
                            "<i>Я запомню эту информацию для будущих диалогов.</i>"
                        )
                elif context.machine_type:
                    # Информация о станке
                    machine_info = knowledge_service.find_machine(context.machine_type) if knowledge_service else None
                    if machine_info:
                        response = (
                            f"🏭 <b>Информация о станке:</b>\n\n"
                            f"<b>Тип:</b> {machine_info.machine_type}\n"
                        )
                        if machine_info.power_kw:
                            response += f"<b>Мощность:</b> {machine_info.power_kw} кВт\n"
                        if machine_info.max_rpm:
                            response += f"<b>Макс. обороты:</b> {machine_info.max_rpm} об/мин\n"
                        await message.answer(response)
                    else:
                        await message.answer(
                            f"🏭 <b>Станок:</b> {context.machine_type}\n\n"
                            f"💡 <i>Этот станок сохранён в базу знаний.</i>\n"
                            f"Если у вас есть дополнительная информация о нём, поделитесь — я учту её в рекомендациях."
                        )
                else:
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏭 Указать станок", callback_data="select_machine")], [InlineKeyboardButton(text="📖 Помощь", callback_data="nav_help")]])
                    await message.answer("🤔 <b>Станок не указан.</b>\n\nРасскажите на каком станке работаете или нажмите кнопку.", reply_markup=kb)
            
            elif context.recommended_vc:  # Если уже была рекомендация
                # Пользователь описывает свои параметры
                await handle_user_experience(message, context, user_text)
                # Сохраняем контекст после сохранения опыта (с проверкой user_id)
                save_context_safe(context, user_id)
            else:
                # Проверяем состояние FSM - если COLLECTING_PARAMS, НЕ говорим "не понял"
                fsm_state = handler.state_machine.determine_state(context) if handler and handler.state_machine else None
                
                if fsm_state == SystemState.COLLECTING_PARAMS:
                    # В состоянии сбора параметров - показываем что приняли и просим уточнить
                    await message.answer(
                        "✅ <b>Принял.</b>\n\n"
                        "💬 <b>Уточните параметры:</b>\n"
                        "• Материал\n"
                        "• Диаметры и размеры\n"
                        "• Количество\n"
                        "• Станок (если известен)\n\n"
                        "<i>Можно указать всё одним сообщением.</i>",
                        reply_markup=create_main_nav_keyboard()
                    )
                    save_context_safe(context, user_id)
                else:
                    # Просто не поняли - отправляем сообщение с подсказками
                    handler_message = result.get('message', '')
                    if handler_message:
                        await message.answer(handler_message, reply_markup=create_main_nav_keyboard())
                    else:
                        await message.answer(
                            "🤔 <b>Не совсем понял.</b>\n\n"
                            "💬 <i>Опишите задачу подробнее, например:</i>\n"
                            "<code>\"Сталь, токарный ЧПУ, снять с Ø100 до Ø90, черновая обработка\"</code>\n\n"
                            "Или используйте команды:\n"
                            "• <code>сохранить работу</code> - сохранить текущую задачу\n"
                            "• <code>мои работы</code> - список сохранённых работ\n"
                            "• <code>работа W001</code> - загрузить работу по номеру",
                            reply_markup=create_main_nav_keyboard()
                        )
                    save_context_safe(context, user_id)
    
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        metrics.total_errors += 1
        await message.answer(
            f"❌ <b>Произошла ошибка</b>\n\n"
            f"Попробуйте описать задачу заново или нажмите /start"
        )
    finally:
        # Обновляем метрики времени ответа (используем sync версию для обратной совместимости)
        response_time = time.time() - start_time
        if hasattr(metrics, 'add_response_time_sync'):
            metrics.add_response_time_sync(response_time)
        else:
            metrics.add_response_time(response_time)


async def handle_user_experience(message: types.Message, context: Context, user_text: str):
    """Обработать опыт оператора и сохранить его."""
    try:
        from app.core.parser import TextParser
        parser = TextParser()
        
        # Парсим параметры из текста
        parsed = parser.parse(user_text)
        
        # Извлекаем числовые параметры
        user_params = {}
        
        # Простой парсинг числовых значений (в т.ч. "обороты 2000", "скорость резания 120", "сьем 2 мм")
        import re
        low = user_text.lower()

        # VC: vc=120, 120 м/мин, скорость резания 120, скорость 120
        vc_match = (
            re.search(r'vc[=\s:]*(\d+(?:[.,]\d+)?)', low) or
            re.search(r'скорость\s*(?:резания)?\s*(?:примерно\s*)?[:\s]*(\d+(?:[.,]\d+)?)', low) or
            re.search(r'(\d+(?:[.,]\d+)?)\s*(?:м\s*в\s*минуту|м/мин)', low)
        )
        if vc_match:
            user_params['vc'] = float((vc_match.group(1) or '').replace(',', '.'))

        # RPM: rpm=2000, 2000 об, обороты 2000, 2000 оборотов
        rpm_match = (
            re.search(r'rpm[=\s:]*(\d+)', low) or
            re.search(r'оборот[а-я]*\s*(?:примерно\s*)?[:\s]*(\d+)', low) or
            re.search(r'(\d+)\s*(?:об(?:орот)?|об/мин)', low) or
            re.search(r'максимум\s*(?:оборот[а-я]*\s*)?(\d+)', low)
        )
        if rpm_match:
            user_params['rpm'] = float(rpm_match.group(1))

        # Feed: подача 0.2, feed=0.2
        feed_match = re.search(r'подач[аиу]\s*(?:примерно\s*)?[:\s]*(\d+(?:[.,]\d+)?)|feed[=\s:]*(\d+(?:[.,]\d+)?)', low)
        if feed_match:
            user_params['feed'] = float((feed_match.group(1) or feed_match.group(2) or '').replace(',', '.'))

        # AP: глубина 2, ap=2, сьем/съём около 2 мм, около 2 мм
        ap_match = (
            re.search(r'глубин[ау]\s*(?:примерно\s*)?[:\s]*(\d+(?:[.,]\d+)?)', low) or
            re.search(r'ap[=\s:]*(\d+(?:[.,]\d+)?)', low) or
            re.search(r'сьем|съём|съем', low) and re.search(r'(?:около\s*)?(\d+(?:[.,]\d+)?)\s*мм', low) or
            re.search(r'(?:около|даю|ставлю)\s*(\d+(?:[.,]\d+)?)\s*мм', low) or
            re.search(r'(\d+(?:[.,]\d+)?)\s*мм\s*(?:глубин|съем|сьем|съём)', low)
        )
        if ap_match and ap_match.lastindex and ap_match.group(1):
            user_params['ap'] = float((ap_match.group(1) or '').replace(',', '.'))
        
        if user_params:
            session = get_session(DB_URL)
            try:
                save_user_decision(
                    session=session,
                    user_id=str(message.from_user.id),
                    geometry={
                        "diameter_start_mm": context.diameter_start or 0,
                        "diameter_end_mm": context.diameter_end or 0,
                        "length_mm": context.length or 0,
                    },
                    operation={"operation_type": context.operation or "roughing"},
                    bot_recommendation={
                        "vc": context.recommended_vc or 0,
                        "rpm": context.recommended_rpm or 0,
                        "feed": context.recommended_feed or 0,
                        "ap": context.recommended_ap or 0,
                    },
                    user_actual={
                        "rpm": user_params.get("rpm") or 0,
                        "feed": user_params.get("feed") or 0,
                        "ap": user_params.get("ap") or 0,
                    },
                    comparison_choice="custom",
                    source="telegram",
                    session_id=context.session_id,
                    full_context=context.to_dict(),
                )
            except Exception as e:
                logger.error(f"Error saving user decision: {e}", exc_info=True)
                session.rollback()
            finally:
                session.close()
            
            lang = get_lang(context)
            await message.answer(t('msg.thanks_saved', lang=lang))
        else:
            lang = get_lang(context)
            await message.answer(t('msg.describe_params', lang=lang))
    
    except Exception as e:
        logger.error(f"Error saving experience: {e}", exc_info=True)
        await message.answer(t('msg.save_failed', lang=get_lang(context)))


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ И ЗАПУСК
# ============================================================================

async def load_standards_on_startup():
    """Загрузить стандарты при старте бота."""
    try:
        logger.info("📐 Автозагрузка стандартов...")
        from standards.loader import load_all_standards
        
        results = load_all_standards(force_refresh=False)
        
        if results["loaded"]:
            logger.info("✅ Стандарты загружены:")
            for item in results["loaded"]:
                logger.info(f"   • {item}")
        
        if results["warnings"]:
            for warning in results["warnings"]:
                logger.warning(f"⚠️  {warning}")
        
        if results["errors"]:
            for error in results["errors"]:
                logger.error(f"❌ {error}")
        
    except ImportError as e:
        logger.warning(f"⚠️  Модуль стандартов недоступен: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Ошибка при загрузке стандартов: {e}")
        logger.exception("Ошибка автозагрузки стандартов")


async def load_standards_on_startup():
    """Загрузить стандарты при старте бота."""
    try:
        logger.info("📐 Автозагрузка стандартов...")
        from standards.loader import load_all_standards
        
        results = load_all_standards(force_refresh=False)
        
        if results["loaded"]:
            logger.info("✅ Стандарты загружены:")
            for item in results["loaded"]:
                logger.info(f"   • {item}")
        
        if results["warnings"]:
            for warning in results["warnings"]:
                logger.warning(f"⚠️  {warning}")
        
        if results["errors"]:
            for error in results["errors"]:
                logger.error(f"❌ {error}")
        
    except ImportError as e:
        logger.warning(f"⚠️  Модуль стандартов недоступен: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Ошибка при загрузке стандартов: {e}")
        logger.exception("Ошибка автозагрузки стандартов")


async def initialize_services():
    """Инициализация всех сервисов."""
    global knowledge_service, handler, image_parser, context_repository, db_pool
    
    logger.info("🚀 Инициализация сервисов...")
    
    # 0. Загрузка стандартов (ГОСТ, ОСТ, ISO и т.д.)
    await load_standards_on_startup()
    
    # 1. Database Pool (для масштабируемости)
    logger.info("🗄️ Инициализация пула соединений БД...")
    from app.services.database_pool import DatabasePool
    db_pool = DatabasePool(
        db_url=DB_URL,
        pool_size=5,
        max_overflow=10
    )
    
    # Инициализируем БД
    # Инициализация базы данных
    init_orm_database(DB_URL)
    
    # Запуск миграций для добавления недостающих столбцов
    logger.info("🔄 Запуск миграций базы данных...")
    try:
        run_all_migrations(str(db_path))
        logger.info("✅ Миграции выполнены успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении миграций: {e}")
        # Не прерываем запуск, но логируем ошибку
    
    # 2. Context Repository (для персистентного хранения контекста)
    logger.info("💾 Инициализация репозитория контекста...")
    from app.services.context_repository import ContextRepository
    with db_pool.get_session() as session:
        context_repository = ContextRepository(db_session=session)
    
    # 3. Knowledge Service
    logger.info("📚 Загрузка базы знаний...")
    knowledge_service = KnowledgeService()
    await knowledge_service.initialize()
    
    # 4. Image Parser
    logger.info("📸 Инициализация парсера изображений...")
    image_parser = ImageParser(tesseract_cmd=TESSERACT_CMD)
    if image_parser.ocr_available:
        logger.info("✅ OCR готов к работе (Tesseract доступен)")
    else:
        logger.warning("⚠️ OCR недоступен (Tesseract не найден или не настроен)")
    
    # 5. Message Handler
    logger.info("📨 Инициализация обработчика сообщений...")
    
    # Используем пул соединений для handler
    db_session = db_pool.get_session_direct()
    
    handler = MessageHandler(
        knowledge_service=knowledge_service,
        db_session=db_session,
        tesseract_cmd=TESSERACT_CMD
    )
    
    logger.info("✅ Все сервисы инициализированы")


async def cleanup_contexts_periodically():
    """Периодическая очистка истекших контекстов."""
    while True:
        try:
            await asyncio.sleep(3600)  # Каждый час
            if context_manager:
                cleaned = context_manager.cleanup_expired()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} expired contexts")
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


async def main():
    """Главная функция запуска бота."""
    global context_manager, rate_limiter, file_storage
    
    # Инициализация менеджера контекстов
    max_contexts = int(os.getenv("MAX_CONTEXTS", "1000"))
    ttl_hours = int(os.getenv("CONTEXT_TTL_HOURS", "24"))
    context_manager = ContextManager(max_contexts=max_contexts, ttl_hours=ttl_hours)
    logger.info(f"ContextManager initialized: max_contexts={max_contexts}, ttl_hours={ttl_hours}")
    
    # Инициализация rate limiter
    max_messages = int(os.getenv("RATE_LIMIT_MAX_MESSAGES", "10"))
    per_seconds = int(os.getenv("RATE_LIMIT_PER_SECONDS", "60"))
    rate_limiter = RateLimiter(max_messages=max_messages, per_seconds=per_seconds)
    logger.info(f"RateLimiter initialized: max_messages={max_messages}, per_seconds={per_seconds}")
    
    # Инициализация файлового хранилища (опционально)
    storage_dir = os.getenv("CONTEXT_STORAGE_DIR", "contexts")
    if storage_dir:
        file_storage = FileContextStorage(storage_dir=storage_dir)
        logger.info(f"FileContextStorage initialized: storage_dir={storage_dir}")
    
    # Запускаем задачу периодической очистки контекстов
    cleanup_task = asyncio.create_task(cleanup_contexts_periodically())
    
    print("=" * 60)
    print("🚀 Запуск AI-бота CNC Assistant")
    print("🧠 Режим: естественный диалог с пониманием контекста")
    print(f"🤖 Токен: {BOT_TOKEN[:10]}...")
    print("=" * 60)
    
    try:
        # Инициализация сервисов
        await initialize_services()
        
        # Проверка соединения с Telegram
        me = await bot.get_me()
        print(f"✅ Бот: @{me.username} (ID: {me.id})")
        
        # Запускаем опрос
        print("\n🔄 Бот запущен и ожидает сообщений...")
        print("💬 Режим: естественный диалог без кнопок")
        print("🧠 Контекст сохраняется между сообщениями")
        print("📊 Сбор опыта операторов для обучения ИИ")
        print("⚠️ Для остановки нажмите Ctrl+C\n")
        
        await dp.start_polling(bot, skip_updates=True)
    
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"\n❌ Фатальная ошибка: {e}")
        logger.error(f"Фатальная ошибка: {e}", exc_info=True)
