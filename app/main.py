"""
Точка входа в приложение CNC Assistant.
Инициализация: bot + knowledge + storage + core
Новая архитектура с Context, Parser, Assumptions, KnowledgeService.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

# Настройка логирования
os.makedirs("logs", exist_ok=True)
os.makedirs("app/knowledge/knowledge_base", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/cnc_assistant.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Глобальные переменные для доступа к компонентам
bot_instance = None
knowledge_service_instance = None
handler_instance = None


@asynccontextmanager
async def lifespan():
    """
    Управление жизненным циклом приложения.
    Инициализация при старте, очистка при остановке.
    """
    global bot_instance, knowledge_service_instance, handler_instance

    logger.info("🚀 Starting CNC Assistant...")

    try:
        # Инициализация компонентов в правильном порядке
        
        # 1. Сервис знаний (загружает справочные данные)
        logger.info("📚 Loading knowledge base...")
        from app.services.knowledge_service import KnowledgeService
        knowledge_service = KnowledgeService()
        await knowledge_service.initialize()
        knowledge_service_instance = knowledge_service

        # 2. Основные движки расчета
        logger.info("⚙️ Initializing calculation engines...")
        from app.core.calculator import PhysicsCalculator, CuttingParametersCalculator
        from app.core.pass_strategy import PassStrategy
        from app.core.validator import Validator
        from app.core.assumptions import AssumptionEngine
        
        # Калькуляторы - статические классы, не требуют knowledge_service
        calculator = PhysicsCalculator()
        params_calculator = CuttingParametersCalculator()
        
        # PassStrategy и Validator могут требовать knowledge_service, но пока используем без него
        pass_strategy = None  # Будет создан при необходимости
        validator = Validator()
        assumption_engine = AssumptionEngine(knowledge_service)

        # 3. Машина состояний (пока не используется в новой архитектуре)
        state_machine = None

        # 4. Главный обработчик сообщений
        logger.info("📨 Initializing message handler...")
        from app.bot.handler import MessageHandler
        handler = MessageHandler(
            knowledge_service=knowledge_service,
            calculator=calculator,
            pass_strategy=pass_strategy,
            validator=validator,
            assumption_engine=assumption_engine
        )
        handler_instance = handler

        # 5. Телеграм бот (AI-версия без кнопок)
        logger.info("🤖 Initializing AI Telegram bot...")
        from app.bot import ai_bot
        
        # Используем новый AI-бот с пониманием контекста
        bot_instance = ai_bot

        logger.info("✅ CNC Assistant initialized successfully!")

        yield {
            'handler': handler,
            'knowledge_service': knowledge_service,
            'calculator': calculator,
            'params_calculator': params_calculator,
            'validator': validator,
            'assumption_engine': assumption_engine,
            'bot': bot_instance
        }

    except Exception as e:
        logger.error(f"❌ Failed to initialize CNC Assistant: {e}", exc_info=True)
        raise

    finally:
        logger.info("🛑 Shutting down CNC Assistant...")
        logger.info("👋 CNC Assistant stopped")


async def main():
    """Основная функция запуска приложения."""
    async with lifespan() as components:
        try:
            # Получаем бота из компонентов
            bot = components['bot']

            # Запускаем AI-бота в режиме polling
            logger.info("🟢 Starting AI bot in polling mode...")
            logger.info("💬 Режим: естественный диалог без кнопок")
            logger.info("🧠 Контекст сохраняется между сообщениями")
            await bot.main()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)
            raise


def run():
    """Запуск приложения (для poetry/scripts)."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")


if __name__ == "__main__":
    run()