#!/usr/bin/env python3
"""
Точка входа в систему.
Выбирает режим работы: Telegram или CLI.
"""
import asyncio
import sys
from typing import Optional

from app.bot.telegram_bot import start_telegram_bot
from app.bot.cli_bot import start_cli_bot


async def main():
    """Запуск бота в нужном режиме."""
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        print("Запуск в режиме CLI...")
        await start_cli_bot()
    else:
        print("Запуск Telegram бота...")
        await start_telegram_bot()


if __name__ == "__main__":
    asyncio.run(main())