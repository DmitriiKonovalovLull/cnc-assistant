"""
Главный модуль Telegram бота - точка входа и инициализация.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Загрузка .env
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Загружен .env из: {env_path}")
else:
    print(f"❌ Файл .env не найден: {env_path}")
    sys.exit(1)

# Импорты
from app.core.context import Context
from app.core.image_parser import ImageParser
from app.services.knowledge_service import KnowledgeService
from app.bot.handler import MessageHandler
from app.bot.context_manager import (
    ContextManager, RateLimiter, FileContextStorage
)
from app.storage.models import init_orm_database
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

# Путь к базе данных
db_path = project_root / "app" / "storage" / "cnc.db"
db_path.parent.mkdir(parents=True, exist_ok=True)
if os.name == 'nt':  # Windows
    DB_URL = f"sqlite:///{str(db_path).replace(chr(92), '/')}"
else:  # Unix/Linux/Mac
    DB_URL = f"sqlite:///{db_path.as_posix()}"

# Константы
MAX_TELEGRAM_MESSAGE_LENGTH = 4096  # Ограничение Telegram API
TELEGRAM_SAFE_MESSAGE_LENGTH = 4000  # Безопасная длина с запасом

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


# Глобальные сервисы (инициализируются при старте)
knowledge_service: Optional[KnowledgeService] = None
handler: Optional[MessageHandler] = None
image_parser: Optional[ImageParser] = None
context_repository: Optional[Any] = None  # ContextRepository
db_pool: Optional[Any] = None  # DatabasePool

# Хранилище контекстов пользователей (в памяти, для обратной совместимости)
user_contexts: Dict[str, Context] = {}

# Менеджер контекстов с ограничениями и очисткой
context_manager: Optional[ContextManager] = None

# Rate limiter для защиты от спама
rate_limiter: Optional[RateLimiter] = None

# Файловое хранилище контекстов (опционально)
file_storage: Optional[FileContextStorage] = None


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
    init_orm_database(DB_URL)
    
    # Запуск миграций
    logger.info("🔄 Запуск миграций базы данных...")
    try:
        run_all_migrations(str(db_path))
        logger.info("✅ Миграции выполнены успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении миграций: {e}")
    
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


async def initialize_bot_services():
    """Инициализация сервисов бота (вызывается из main)."""
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
    asyncio.create_task(cleanup_contexts_periodically())


async def main():
    """Основная функция запуска."""
    print("=" * 60)
    print("🚀 Запуск AI-бота CNC Assistant")
    print("🧠 Режим: естественный диалог с пониманием контекста")
    print(f"🤖 Токен: {BOT_TOKEN[:10]}...")
    print("=" * 60)
    
    try:
        # Инициализация сервисов бота
        await initialize_bot_services()
        
        # Инициализация основных сервисов
        await initialize_services()
        
        # Регистрация обработчиков
        from app.bot.telegram_bot.handlers import (
            register_commands,
            register_message_handlers,
            register_photo_handlers,
            register_callback_handlers
        )
        
        register_commands(dp)
        register_message_handlers(dp)
        register_photo_handlers(dp)
        register_callback_handlers(dp)
        
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
