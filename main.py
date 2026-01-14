"""
Запуск бота Дня 1 - чистый и простой.
"""

import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

print("=" * 50)
print("🤖 CNC Assistant - День 1")
print("=" * 50)
print("Цель: Бот, который думает как человек")
print("=" * 50)

from bot.telegram_bot import main

if __name__ == "__main__":
    main()