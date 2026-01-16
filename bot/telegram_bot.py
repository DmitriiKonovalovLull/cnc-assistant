"""
🏁 CNC Assistant — рабочая версия
python-telegram-bot >= 20
"""

import os
import sys
import math
import yaml
import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================== PATHS ====================

ROOT_DIR = Path(__file__).parent.parent
RULES_FILE = ROOT_DIR / "data" / "rules" / "cutting_modes.yaml"

sys.path.insert(0, str(ROOT_DIR))

# ==================== LOAD ENV ====================

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ TELEGRAM_TOKEN не найден")
    sys.exit(1)

# ==================== LOAD YAML ====================

with open(RULES_FILE, "r", encoding="utf-8") as f:
    RULES = yaml.safe_load(f)

# ==================== HELPERS ====================

def find_material(text: str):
    for key, mat in RULES["materials"].items():
        if key in text:
            return key, mat
    return None, None


def find_operation(text: str):
    for key, op in RULES["operations"].items():
        if key in text:
            return key, op
    return None, None


def find_mode(text: str):
    if "чернов" in text:
        return "roughing", RULES["modes"]["roughing"]
    if "чистов" in text:
        return "finishing", RULES["modes"]["finishing"]
    return "roughing", RULES["modes"]["roughing"]


def extract_diameter(text: str):
    import re
    m = re.search(r"(\d+)", text)
    return float(m.group(1)) if m else None


def calculate_rpm(vc, d):
    return int((1000 * vc) / (math.pi * d))


# ==================== CORE LOGIC ====================

def process_request(text: str) -> str:
    text = text.lower()

    mat_key, mat = find_material(text)
    op_key, op = find_operation(text)
    mode_key, mode = find_mode(text)
    diameter = extract_diameter(text)

    if not mat or not op or not diameter:
        return (
            "❌ Не хватает данных\n\n"
            "Пример:\n"
            "• steel turning 50 roughing\n"
            "• aluminum milling 20 finishing"
        )

    vc = mat["cutting_speed"]["default"]
    feed = mat["feed"]["default"] * mode["feed_multiplier"]
    rpm = calculate_rpm(vc, diameter)

    return (
        f"⚙️ **{mat['name']} — {op['name']}**\n\n"
        f"🛠 Инструмент: {op['default_tool']}\n"
        f"📐 Диаметр: {diameter} мм\n"
        f"🎯 Режим: {mode['name']}\n\n"
        f"📊 **Режимы:**\n"
        f"• Vc: {vc} м/мин\n"
        f"• n: {rpm} об/мин\n"
        f"• Подача: {feed:.2f} мм/об\n\n"
        f"💡 {mat.get('notes', '')}"
    )

# ==================== TELEGRAM HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 CNC Assistant\n\n"
        "Пример:\n"
        "steel turning 50 roughing\n"
        "aluminum milling 20 finishing"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Формат:\n"
        "<material> <operation> <diameter> <mode>\n\n"
        "materials: steel aluminum titanium\n"
        "operations: turning milling\n"
        "modes: roughing finishing"
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = process_request(update.message.text)
    await update.message.reply_text(response)

# ==================== MAIN ====================

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))

    print("✅ CNC Assistant запущен")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())