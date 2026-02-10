"""
AI-подобный Telegram бот без кнопок.
Понимает контекст, ведет естественный диалог, делает предположения.
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
from aiogram.fsm.state import State, StatesGroup

# Импорты новой архитектуры
from app.core.context import Context, DataSource
from app.core.parser import TextParser
from app.core.image_parser import ImageParser
from app.core.assumptions import AssumptionEngine
from app.services.knowledge_service import KnowledgeService
from app.services.tool_saver import ToolSaver
from app.services.recommendation import get_turning_recommendation
from app.bot.handler import MessageHandler
from app.storage.models import init_orm_database, get_session

# Настройка логирования
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(logs_dir / "ai_bot.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
    logger.error("❌ Токен не найден! Проверьте .env файл")
    sys.exit(1)

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

# Хранилище контекстов пользователей (в памяти, можно перенести в БД)
user_contexts: Dict[str, Context] = {}


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
    lines.append("💬 <i>Как вы делаете на практике? Расскажите, какие параметры используете.</i>")
    
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
    
    # Создаем новый контекст для пользователя
    context = Context()
    context.user_id = user_id
    context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    user_contexts[user_id] = context
    
    welcome_text = (
        "👋 <b>Привет! Я CNC Assistant — твой ИИ-помощник для подбора режимов резания.</b>\n\n"
        "💬 <b>Просто опиши задачу в свободной форме:</b>\n\n"
        "• <i>\"Сталь, токарный ЧПУ, снять с Ø100 до Ø90\"</i>\n"
        "• <i>\"Алюминий, черновая обработка, станок 11 кВт\"</i>\n"
        "• <i>\"Проточить нержавейку, радиус пластины 0.8 мм\"</i>\n\n"
        "🧠 <b>Я понимаю контекст</b> и делаю разумные предположения.\n"
        "📸 <b>Можешь отправить фото инструмента</b> — я распознаю его.\n\n"
        "💡 <i>Начни с описания задачи, и я помогу подобрать режимы резания.</i>"
    )
    
    await message.answer(welcome_text)


@dp.message(F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Обработка фотографий инструментов."""
    user_id = str(message.from_user.id)
    
    # Получаем или создаем контекст
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
        
        parse_result = image_parser.parse_tool_image(image_bytes)
        
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
            
            # Сохраняем контекст
            user_contexts[user_id] = context
        
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
    user_text = message.text or ""
    
    # Получаем или создаем контекст
    context = user_contexts.get(user_id)
    if not context:
        context = Context()
        context.user_id = user_id
        context.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        user_contexts[user_id] = context
    
    try:
        # Обрабатываем сообщение через handler
        if not handler:
            await message.answer(
                "❌ Бот не инициализирован. Перезапустите бота."
            )
            return
        
        # Обрабатываем сообщение
        result = await handler.process_message(
            user_text=user_text,
            user_id=user_id,
            session_id=context.session_id,
            existing_context=context
        )
        
        # Обновляем контекст из результата (handler обновляет существующий контекст)
        # Просто сохраняем обновленный контекст обратно
        user_contexts[user_id] = context
        
        # Определяем действие
        action = result.get('action', 'unknown')
        
        if action == 'clarify':
            # Нужно уточнить данные
            missing = result.get('missing_fields', [])
            response = format_clarification_request(context, missing)
            await message.answer(response)
        
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
            
            # Сохраняем обновленный контекст
            user_contexts[user_id] = context
        
        elif action == 'error':
            # Ошибка
            error_msg = result.get('message', 'Произошла ошибка')
            await message.answer(
                f"❌ <b>Ошибка</b>\n\n{error_msg}\n\n"
                f"💡 <i>Попробуйте описать задачу по-другому.</i>"
            )
        
        else:
            # Неизвестное действие
            await message.answer(
                "🤔 <b>Не совсем понял.</b>\n\n"
                "💬 <i>Опиши задачу подробнее, например:</i>\n"
                "<code>\"Сталь, токарный ЧПУ, снять с Ø100 до Ø90, черновая обработка\"</code>"
            )
    
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>Произошла ошибка</b>\n\n"
            f"Попробуйте описать задачу заново или нажмите /start"
        )


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ И ЗАПУСК
# ============================================================================

async def initialize_services():
    """Инициализация всех сервисов."""
    global knowledge_service, handler, image_parser
    
    logger.info("🚀 Инициализация сервисов...")
    
    # 1. Knowledge Service
    logger.info("📚 Загрузка базы знаний...")
    knowledge_service = KnowledgeService()
    await knowledge_service.initialize()
    
    # 2. Image Parser
    logger.info("📸 Инициализация парсера изображений...")
    image_parser = ImageParser()
    
    # 3. Message Handler
    logger.info("📨 Инициализация обработчика сообщений...")
    
    # Создаем сессию БД для tool_saver
    DB_URL = "sqlite:///app/storage/cnc.db"
    init_orm_database(DB_URL)
    db_session = get_session(DB_URL)
    
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
