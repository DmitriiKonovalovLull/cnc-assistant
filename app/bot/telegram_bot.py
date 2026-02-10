"""
AI-подобный Telegram бот без кнопок.
Понимает контекст, ведет естественный диалог, делает предположения.
Собирает реальный опыт операторов для обучения ИИ.
"""

import asyncio
import logging
import os
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
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты новой архитектуры
from app.core.context import Context, DataSource
from app.core.parser import TextParser
from app.core.image_parser import ImageParser
from app.core.assumptions import AssumptionEngine
from app.services.knowledge_service import KnowledgeService
from app.services.tool_saver import ToolSaver
from app.services.recommendation import get_turning_recommendation
from app.bot.handler import MessageHandler
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
TESSERACT_CMD = os.getenv("TESSERACT_CMD") or os.getenv("TESSERACT_PATH")

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

# Глобальные сервисы (инициализируются при старте)
knowledge_service: Optional[KnowledgeService] = None
handler: Optional[MessageHandler] = None
image_parser: Optional[ImageParser] = None
context_repository: Optional[Any] = None  # ContextRepository
db_pool: Optional[Any] = None  # DatabasePool

# Хранилище контекстов пользователей (в памяти, для обратной совместимости)
# В будущем будет использоваться только context_repository
user_contexts: Dict[str, Context] = {}


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


def save_context_safe(context: Context, user_id: str) -> None:
    """
    Безопасно сохранить контекст с проверкой user_id.
    
    Args:
        context: Контекст для сохранения
        user_id: ID пользователя
    """
    ensure_context_user_id(context, user_id)
    if context_repository:
        context_repository.save_context(context)
    else:
        user_contexts[user_id] = context


# ============================================================================
# ФОРМАТИРОВАНИЕ СООБЩЕНИЙ
# ============================================================================

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
    
    if context.tool_name:
        lines.append(f"🔧 Инструмент: <b>{context.tool_name}</b>")
    
    if context.assumptions_made:
        lines.append(f"\n💡 <i>Я предположил: {', '.join(context.assumptions_made)}</i>")
    
    if context.overall_confidence > 0:
        confidence_pct = int(context.overall_confidence * 100)
        lines.append(f"🎯 <i>Уверенность: {confidence_pct}%</i>")
    
    return "\n".join(lines) if lines else "Пока нет данных..."


def format_recommendation(recommendation: Dict[str, Any], context: Context) -> str:
    """Форматировать рекомендацию в естественном виде."""
    lines = []
    
    lines.append("🎯 <b>РЕКОМЕНДУЮ:</b>")
    lines.append("")
    
    # Основные параметры
    vc = recommendation.get('vc_m_min') or recommendation.get('vc', 0)
    rpm = recommendation.get('rpm', 0)
    feed = recommendation.get('feed_mm_rev') or recommendation.get('feed', 0)
    ap = recommendation.get('ap_mm') or recommendation.get('ap', 0)
    power = recommendation.get('power_kw', 0)
    
    lines.append(f"⚡ Скорость резания: <code>{vc:.0f} м/мин</code>")
    lines.append(f"🔄 Обороты: <code>{rpm:.0f} об/мин</code>")
    lines.append(f"📏 Подача: <code>{feed:.2f} мм/об</code>")
    lines.append(f"🔪 Глубина: <code>{ap:.1f} мм</code>")
    
    if power > 0:
        lines.append(f"⚙️ Мощность: <code>{power:.1f} кВт</code>")
    
    # Объяснение
    lines.append("")
    lines.append("<b>Почему такие параметры:</b>")
    
    if context.material:
        material_explanations = {
            'сталь': 'Для стали использую средние скорости резания',
            'алюминий': 'Алюминий обрабатывается на высоких скоростях',
            'нержавейка': 'Нержавейка требует более низких скоростей',
            'титан': 'Титан обрабатывается очень аккуратно, низкие скорости'
        }
        explanation = material_explanations.get(context.material.lower(), 'Стандартные параметры для этого материала')
        lines.append(f"• {explanation}")
    
    if context.mode:
        mode_explanations = {
            'черновая': 'Черновая обработка — максимальный съём металла',
            'чистовая': 'Чистовая обработка — акцент на качество поверхности',
            'получистовая': 'Получистовая — баланс между производительностью и качеством'
        }
        explanation = mode_explanations.get(context.mode.lower(), '')
        if explanation:
            lines.append(f"• {explanation}")
    
    # Предупреждения
    warnings = recommendation.get('warnings', [])
    if warnings:
        lines.append("")
        lines.append("⚠️ <b>Обратите внимание:</b>")
        for warning in warnings[:3]:  # Максимум 3 предупреждения
            lines.append(f"• {warning}")
    
    # Предположения
    if context.assumptions_made:
        lines.append("")
        lines.append("💡 <b>Я предположил:</b>")
        for assumption in context.assumptions_made:
            metadata = context.get_field_metadata(assumption)
            if metadata and metadata.reasoning:
                lines.append(f"• {assumption}: {metadata.reasoning}")
    
    lines.append("")
    lines.append("💬 <b>Какие параметры вы используете на практике?</b>")
    lines.append("<i>Опишите свои режимы резания — это поможет улучшить рекомендации.</i>")
    
    return "\n".join(lines)


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

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Начало работы с ботом."""
    await state.clear()
    
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name or "друг"
    
    # Проверяем, есть ли история у пользователя
    if context_repository:
        existing_context = context_repository.get_context(user_id)
    else:
        existing_context = user_contexts.get(user_id)
    has_history = existing_context and (
        existing_context.dialog_history or
        existing_context.material or
        existing_context.machine_type or
        existing_context.tool_name
    )
    
    if has_history:
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
            "• <code>история</code> - показать историю диалога и работы\n"
            "• <code>мои работы</code> - список сохранённых работ\n"
            "• <code>сохранить работу</code> - сохранить текущую задачу\n"
            "• Начать с чистого листа (/start для нового контекста)\n\n"
            "<i>Просто напишите что нужно, я пойму.</i>"
        )
    else:
        # Новая сессия - стандартное приветствие
        welcome_text = (
            f"👋 <b>Привет, {user_name}!</b>\n\n"
            f"Я <b>CNC Assistant</b> — твой ИИ-помощник для подбора режимов резания.\n\n"
            f"💬 <b>Что я умею:</b>\n\n"
            f"• Подбирать режимы резания по описанию задачи\n"
            f"• Распознавать инструменты с фотографий\n"
            f"• Помнить контекст между сообщениями\n"
            f"• Делать разумные предположения\n\n"
            f"📝 <b>Просто опиши задачу в свободной форме:</b>\n\n"
            f"• <i>\"Сталь, токарный ЧПУ, снять с Ø100 до Ø90\"</i>\n"
            f"• <i>\"Алюминий, черновая обработка, станок 11 кВт\"</i>\n"
            f"• <i>\"Проточить нержавейку, радиус пластины 0.8 мм\"</i>\n\n"
            f"💡 <i>Или начни с описания станка, на котором работаешь.</i>"
        )
    
    await message.answer(welcome_text)


@dp.message(F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Обработка фотографий инструментов."""
    user_id = str(message.from_user.id)
    
    # Получаем или создаем контекст
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
        # Получаем самое большое фото
        photo = message.photo[-1]
        
        # Скачиваем фото
        file = await bot.get_file(photo.file_id)
        image_data = await bot.download_file(file.file_path)
        image_bytes = image_data.read()
        
        # Парсим изображение
        if not image_parser:
            await message.answer(
                "❌ OCR не настроен. Установите pytesseract и Pillow для распознавания фотографий."
            )
            return
        
        # Проверяем, что OCR доступен перед парсингом
        if not image_parser or not image_parser.ocr_available:
            await message.answer(
                "⚠️ <b>OCR не настроен</b>\n\n"
                "Для распознавания инструментов с фотографий нужно установить Tesseract OCR.\n\n"
                "📥 <b>Установка:</b>\n"
                "1. Скачайте Tesseract OCR: https://github.com/tesseract-ocr/tesseract\n"
                "2. Установите его в систему\n"
                "3. Добавьте в PATH или укажите путь в настройках\n\n"
                "💡 <i>Пока что вы можете описать инструмент текстом, я пойму.</i>"
            )
            return
        
        parse_result = image_parser.parse_tool_image(image_bytes)
        
        if not parse_result.get('success'):
            # Обработка ошибок парсинга
            error_message = parse_result.get('error', 'Не удалось распознать инструмент на фотографии.')
            
            if 'tesseract' in error_message.lower() or 'ocr' in error_message.lower():
                await message.answer(
                    "⚠️ <b>OCR не настроен</b>\n\n"
                    "Для распознавания инструментов с фотографий нужно установить Tesseract OCR.\n\n"
                    "📥 <b>Установка:</b>\n"
                    "1. Скачайте Tesseract OCR: https://github.com/tesseract-ocr/tesseract\n"
                    "2. Установите его в систему\n"
                    "3. Добавьте в PATH или укажите путь в настройках\n\n"
                    "💡 <i>Пока что вы можете описать инструмент текстом, я пойму.</i>"
                )
            else:
                await message.answer(
                    f"❌ <b>Не удалось распознать инструмент</b>\n\n"
                    f"{error_message}\n\n"
                    f"💡 <i>Попробуйте описать инструмент текстом или отправьте более четкое фото.</i>"
                )
            return
        
        if parse_result.get('success'):
            # Сохраняем инструмент в БД
            tool_id = None
            if handler and handler.tool_saver:
                tool_id = handler.tool_saver.save_tool_from_image(parse_result)
            
            # Обновляем контекст
            if parse_result.get('tool_name'):
                context.set_field(
                    'tool_name',
                    parse_result['tool_name'],
                    DataSource.USER,
                    confidence=parse_result.get('confidence', 0.7),
                    reasoning="Распознано с фотографии инструмента"
                )
            
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
            
            # Формируем ответ
            response_lines = []
            response_lines.append("✅ <b>Инструмент распознан!</b>")
            response_lines.append("")
            
            if parse_result.get('tool_name'):
                response_lines.append(f"📌 <b>Название:</b> <code>{parse_result['tool_name']}</code>")
            
            if parse_result.get('tool_type'):
                response_lines.append(f"🔧 <b>Тип:</b> {parse_result['tool_type']}")
            
            if parse_result.get('manufacturer'):
                response_lines.append(f"🏭 <b>Производитель:</b> {parse_result['manufacturer']}")
            
            if parse_result.get('insert_material'):
                response_lines.append(f"💎 <b>Материал:</b> {parse_result['insert_material']}")
            
            if tool_id:
                response_lines.append("")
                response_lines.append(f"💾 <i>Инструмент сохранён в базу (ID: {tool_id})</i>")
            
            response_lines.append("")
            response_lines.append("💬 <b>Теперь опиши задачу обработки, и я учту этот инструмент.</b>")
            
            await message.answer("\n".join(response_lines))
            
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
        await message.answer(
            f"❌ <b>Ошибка обработки фотографии</b>\n\n"
            f"Попробуйте ещё раз или опишите инструмент текстом."
        )


@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    """Главный обработчик всех текстовых сообщений."""
    user_id = str(message.from_user.id)
    user_text = (message.text or "").strip()
    user_name = message.from_user.first_name or "друг"
    
    # Проверяем на приветствие
    greetings = ['привет', 'здравствуй', 'здравствуйте', 'добрый день', 'добрый вечер', 
                 'доброе утро', 'hi', 'hello', 'hey', 'салют', 'здарова']
    
    is_greeting = any(greeting in user_text.lower() for greeting in greetings)
    
    # Получаем или создаем контекст (используем репозиторий если доступен)
    if context_repository:
        context = context_repository.get_context(user_id)
        if not context:
            context = Context()
            context.user_id = user_id
            context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            context_repository.save_context(context)
        else:
            # Обновляем user_id и session_id если нужно
            ensure_context_user_id(context, user_id)
    else:
        # Fallback на старый способ (в памяти)
        context = user_contexts.get(user_id)
        if not context:
            context = Context()
            context.user_id = user_id
            context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            user_contexts[user_id] = context
        else:
            # Убеждаемся что user_id установлен
            ensure_context_user_id(context, user_id)
    
    # Проверяем запросы на историю и работы (до обработки через handler)
    user_text_lower = user_text.lower().strip()
    
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
            if context.tool_name:
                response_lines.append(f"🔧 Инструмент: {context.tool_name}")
            if context.diameter_start and context.diameter_end:
                response_lines.append(f"📏 Диаметры: Ø{context.diameter_start} → Ø{context.diameter_end} мм")
        
        await message.answer("\n".join(response_lines))
        return
    
    # Если это приветствие - отвечаем дружелюбно
    if is_greeting:
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
            if context.tool_name:
                greeting_response += f"🔧 Инструмент: <b>{context.tool_name}</b>\n"
            
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
            greeting_response = (
                f"👋 <b>Привет, {user_name}!</b>\n\n"
                f"Я <b>CNC Assistant</b> — помогу подобрать режимы резания.\n\n"
                f"💬 <b>С чего начнём?</b>\n\n"
                f"• Опиши задачу обработки\n"
                f"• Расскажи на каком станке работаешь\n"
                f"• Отправь фото инструмента\n\n"
                f"<i>Просто напиши что нужно, я пойму.</i>"
            )
        
        await message.answer(greeting_response)
        return
    
    try:
        # Обрабатываем сообщение через handler
        if not handler:
            await message.answer(
                "❌ Бот не инициализирован. Перезапустите бота."
            )
            return
        
        # Обрабатываем сообщение (передаем существующий контекст)
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
        
        # ПРИОРИТЕТ 1: PROJECT MODE (работа по ГОСТ/чертежу)
        if mode == 'project' or action in ['project_mode', 'standard_part', 'standard_part_unknown']:
            await message.answer(result.get('message', ''))
            # Сохраняем контекст после обработки стандарта (с проверкой user_id)
            save_context_safe(context, user_id)
            return
        
        # ПРИОРИТЕТ 2: Жесткие команды (обрабатываются первыми)
        if is_command or action in ['help', 'capabilities', 'works_list', 'history', 'work_save', 'work_load', 'work_delete']:
            if action == 'help':
                await message.answer(
                    "📖 <b>Помощь по использованию бота</b>\n\n"
                    "🎯 <b>Основная функция:</b>\n"
                    "Подбор режимов резания для токарной и фрезерной обработки.\n\n"
                    "📝 <b>Как описать задачу:</b>\n\n"
                    "Опиши в любом порядке:\n"
                    "• Материал (сталь, алюминий, титан...)\n"
                    "• Диаметры (с Ø100 до Ø90)\n"
                    "• Тип обработки (черновая, чистовая)\n"
                    "• Станок (если известен)\n"
                    "• Инструмент (или отправь фото)\n\n"
                    "💡 <b>Примеры:</b>\n"
                    "<code>Титан, токарный ЧПУ, снять с Ø200 до Ø50</code>\n"
                    "<code>Сталь 45, черновая, Ø100→90</code>\n\n"
                    "🔧 <b>Команды:</b>\n"
                    "• <code>история</code> - история диалога и работы\n"
                    "• <code>мои работы</code> - список сохраненных работ\n"
                    "• <code>сохранить работу</code> - сохранить задачу\n"
                    "• <code>работа W001</code> - загрузить работу\n"
                    "• <code>что ты можешь</code> - описание возможностей\n\n"
                    "💬 <i>Просто опиши задачу — я пойму.</i>"
                )
                return
            
            elif action == 'capabilities':
                await message.answer(
                    "🤖 <b>Я инженерный помощник для токарной и фрезерной обработки.</b>\n\n"
                    "💡 <b>Что я умею:</b>\n\n"
                    "• Подбирать режимы резания (обороты, подачи, глубины)\n"
                    "• Учитывать материал, диаметр и тип обработки\n"
                    "• Адаптироваться под уровень оператора\n"
                    "• Запоминать твои решения и улучшать рекомендации\n"
                    "• Распознавать инструменты с фотографий\n"
                    "• Сохранять работы для быстрого доступа\n\n"
                    "📝 <b>Как работать:</b>\n\n"
                    "Просто опиши задачу в любом порядке:\n"
                    "<i>\"Титан, токарный ЧПУ, снять с Ø200 до Ø50, черновая\"</i>\n\n"
                    "Или используй команды:\n"
                    "• <code>история</code> - показать историю и работы\n"
                    "• <code>мои работы</code> - список сохраненных работ\n"
                    "• <code>сохранить работу</code> - сохранить текущую задачу\n"
                    "• <code>помощь</code> - подробная инструкция\n\n"
                    "💬 <i>Хочешь рассчитать режим — просто напиши параметры.</i>"
                )
                return
            
            # Остальные команды обрабатываются ниже в коде
            # (works_list, history, work_save и т.д. уже обрабатываются)
        
        # Обработка не-инженерных интентов (если не команда)
        if not is_command:
            if action == 'meta_capabilities':
                await message.answer(result.get('message', ''))
                return
            
        if action == 'noise' or action == 'noise_fallback':
            await message.answer(result.get('message', ''))
            return
            
            if action == 'clarify_intent':
                await message.answer(result.get('message', ''))
                return
            
            if action == 'greeting':
                # Приветствие уже обработано выше
                pass
        
        if action == 'clarify':
            # Нужно уточнить данные
            missing = result.get('missing_fields', [])
            
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
                response_lines.append("💬 <i>Можете описать всё в одном сообщении, я пойму.</i>")
                
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
            
            await message.answer(response)
            
            # Сохраняем контекст после уточнения (с проверкой user_id)
            save_context_safe(context, user_id)
        
        elif action == 'calculate':
            # Можно рассчитать
            recommendation = result.get('recommendation', {})
            
            # Показываем что поняли
            summary = format_context_summary(context)
            if summary and summary != "Пока нет данных...":
                await message.answer(f"✅ <b>Понял:</b>\n\n{summary}")
            
            # Показываем рекомендацию
            rec_text = format_recommendation(recommendation, context)
            await message.answer(rec_text)
            
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
                            f"• <code>удалить {work_number}</code> - удалить работу"
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
                        if context.tool_name:
                            response_lines.append(f"🔧 <b>Инструмент:</b> {context.tool_name}")
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
                    await message.answer("🤔 <b>Станок не указан.</b>\n\nРасскажите на каком станке работаете.")
            
            elif context.recommended_vc:  # Если уже была рекомендация
                # Пользователь описывает свои параметры
                await handle_user_experience(message, context, user_text)
                # Сохраняем контекст после сохранения опыта (с проверкой user_id)
                save_context_safe(context, user_id)
            else:
                # Просто не поняли
                await message.answer(
                    "🤔 <b>Не совсем понял.</b>\n\n"
                    "💬 <i>Опиши задачу подробнее, например:</i>\n"
                    "<code>\"Сталь, токарный ЧПУ, снять с Ø100 до Ø90, черновая обработка\"</code>\n\n"
                    "Или используй команды:\n"
                    "• <code>сохранить работу</code> - сохранить текущую задачу\n"
                    "• <code>мои работы</code> - список сохранённых работ\n"
                    "• <code>работа W001</code> - загрузить работу по номеру"
                )
    
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>Произошла ошибка</b>\n\n"
            f"Попробуйте описать задачу заново или нажмите /start"
        )


async def handle_user_experience(message: types.Message, context: Context, user_text: str):
    """Обработать опыт оператора и сохранить его."""
    try:
        from app.core.parser import TextParser
        parser = TextParser()
        
        # Парсим параметры из текста
        parsed = parser.parse(user_text)
        
        # Извлекаем числовые параметры
        user_params = {}
        
        # Простой парсинг числовых значений
        import re
        
        # VC
        vc_match = re.search(r'vc[=\s:]*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:м\s*в\s*минуту|м/мин)', user_text.lower())
        if vc_match:
            user_params['vc'] = float(vc_match.group(1) or vc_match.group(2))
        
        # RPM
        rpm_match = re.search(r'rpm[=\s:]*(\d+)|(\d+)\s*(?:об|оборот)', user_text.lower())
        if rpm_match:
            user_params['rpm'] = float(rpm_match.group(1) or rpm_match.group(2))
        
        # Feed
        feed_match = re.search(r'подач[аиу]\D*(\d+(?:[.,]\d+)?)|feed[=\s:]*(\d+(?:[.,]\d+)?)', user_text.lower())
        if feed_match:
            user_params['feed'] = float(feed_match.group(1) or feed_match.group(2))
        
        # AP
        ap_match = re.search(r'глубин[ау]\D*(\d+(?:[.,]\d+)?)|ap[=\s:]*(\d+(?:[.,]\d+)?)', user_text.lower())
        if ap_match:
            user_params['ap'] = float(ap_match.group(1) or ap_match.group(2))
        
        if user_params:
            # Сохраняем опыт оператора
            session = get_session(DB_URL)
            try:
                save_user_decision(
                    session=session,
                    user_id=int(message.from_user.id),
                    material=context.material or 'неизвестно',
                    operation=context.operation or 'токарка',
                    machine_type=context.machine_type or 'токарный ЧПУ',
                    recommended_vc=context.recommended_vc or 0,
                    recommended_rpm=context.recommended_rpm or 0,
                    recommended_feed=context.recommended_feed or 0,
                    recommended_ap=context.recommended_ap or 0,
                    user_vc=user_params.get('vc'),
                    user_rpm=user_params.get('rpm'),
                    user_feed=user_params.get('feed'),
                    user_ap=user_params.get('ap'),
                    comparison_reason='custom',
                    confidence_level='medium',
                    result='ok'
                )
                session.commit()
            except Exception as e:
                logger.error(f"Error saving user decision: {e}", exc_info=True)
                session.rollback()
            finally:
                session.close()
            
            await message.answer(
                "✅ <b>Спасибо! Ваш опыт сохранён.</b>\n\n"
                "📊 <i>Эти данные помогут улучшить рекомендации для других операторов.</i>\n\n"
                "💬 <i>Можете описать ещё одну задачу или уточнить параметры текущей.</i>"
            )
        else:
            await message.answer(
                "💬 <b>Опишите свои параметры резания:</b>\n\n"
                "Например: <code>\"VC 150 м/мин, 1000 об/мин, подача 0.2, глубина 2 мм\"</code>\n\n"
                "Или просто: <code>\"150, 1000, 0.2, 2\"</code>"
            )
    
    except Exception as e:
        logger.error(f"Error saving experience: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Не удалось сохранить опыт</b>\n\n"
            "Попробуйте описать параметры по-другому."
        )


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ И ЗАПУСК
# ============================================================================

async def initialize_services():
    """Инициализация всех сервисов."""
    global knowledge_service, handler, image_parser, context_repository, db_pool
    
    logger.info("🚀 Инициализация сервисов...")
    
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
        db_session=db_session
    )
    
    logger.info("✅ Все сервисы инициализированы")


async def main():
    """Основная функция запуска."""
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
