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

# ==================== DATABASE INTEGRATION ====================

try:
    from core.memory import session, user_data
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ Модуль core.memory не найден, работаем без сохранения данных")
    DB_AVAILABLE = False

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
    if "чернов" in text or "rough" in text:
        return "roughing", RULES["modes"]["roughing"]
    if "чистов" in text or "finish" in text:
        return "finishing", RULES["modes"]["finishing"]
    return "roughing", RULES["modes"]["roughing"]


def extract_diameter(text: str):
    import re
    m = re.search(r"(\d+)", text)
    return float(m.group(1)) if m else None


def calculate_rpm(vc, d):
    return int((1000 * vc) / (math.pi * d))

# ==================== CORE LOGIC ====================

def process_request(text: str) -> tuple:
    """Обрабатывает запрос и возвращает (ответ, данные_для_сохранения)"""
    text = text.lower()

    mat_key, mat = find_material(text)
    op_key, op = find_operation(text)
    mode_key, mode = find_mode(text)
    diameter = extract_diameter(text)

    if not mat or not op or not diameter:
        response = (
            "❌ Не хватает данных\n\n"
            "Пример:\n"
            "• steel turning 50 roughing\n"
            "• aluminum milling 20 finishing"
        )
        return response, None

    vc = mat["cutting_speed"]["default"]
    feed = mat["feed"]["default"] * mode["feed_multiplier"]
    rpm = calculate_rpm(vc, diameter)

    response = (
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

    # Данные для сохранения
    data_for_save = {
        "material": mat_key,
        "material_name": mat["name"],
        "diameter": diameter,
        "operation": op_key,
        "operation_name": op["name"],
        "mode": mode_key,
        "mode_name": mode["name"],
        "cutting_speed": vc,
        "feed": feed,
        "rpm": rpm
    }

    return response, data_for_save

# ==================== TELEGRAM HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 CNC Assistant\n\n"
        "Примеры запросов:\n"
        "• steel turning 50 roughing\n"
        "• aluminum milling 20 finishing\n"
        "• сталь точение 50 черновая\n"
        "• алюминий фрезерование 20 чистовая"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Формат запроса:\n"
        "<материал> <операция> <диаметр> <режим>\n\n"
        "📌 Материалы: steel, aluminum, titanium (сталь, алюминий, титан)\n"
        "📌 Операции: turning, milling (точение, фрезерование)\n"
        "📌 Режимы: roughing, finishing (черновая, чистовая)\n\n"
        "Используйте команду /history для просмотра истории запросов"
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response, data = process_request(update.message.text)
    
    # Сохраняем данные если доступна БД
    if DB_AVAILABLE and data:
        user_id = update.effective_user.id
        
        try:
            # Обновляем сессию
            session.update(
                user_id,
                material=data["material"],
                diameter=data["diameter"],
                operation=data["operation"],
                mode=data["mode"]
            )
            
            # Сохраняем в базу данных
            user_data.register_job(user_id, {
                "material": data["material"],
                "material_name": data["material_name"],
                "diameter": data["diameter"],
                "operation": data["operation"],
                "operation_name": data["operation_name"],
                "mode": data["mode"],
                "mode_name": data["mode_name"],
                "cutting_speed": data["cutting_speed"],
                "feed": data["feed"],
                "rpm": data["rpm"],
                "query_text": update.message.text
            })
            response += "\n\n💾 Данные сохранены в историю"
            
        except Exception as e:
            print(f"⚠️ Ошибка сохранения данных: {e}")
            response += f"\n\n⚠️ Не удалось сохранить данные: {e}"
    
    await update.message.reply_text(response)

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю запросов пользователя"""
    if not DB_AVAILABLE:
        await update.message.reply_text("⚠️ История запросов недоступна (модуль БД не найден)")
        return
    
    user_id = update.effective_user.id
    
    try:
        # Получаем историю из базы данных
        history = user_data.get_user_jobs(user_id)
        
        if not history:
            await update.message.reply_text("📭 У вас пока нет сохраненных запросов")
            return
        
        response = "📜 **История ваших запросов:**\n\n"
        
        for i, job in enumerate(history[-10:], 1):  # Последние 10 записей
            response += (
                f"{i}. {job['material_name']} — {job['operation_name']}\n"
                f"   Диаметр: {job['diameter']} мм | Режим: {job['mode_name']}\n"
                f"   RPM: {job['rpm']} | Подача: {job['feed']:.2f} мм/об\n\n"
            )
        
        await update.message.reply_text(response)
        
    except Exception as e:
        print(f"⚠️ Ошибка получения истории: {e}")
        await update.message.reply_text(f"⚠️ Ошибка при получении истории: {e}")

# ==================== MAIN ====================

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))

    print("✅ CNC Assistant запущен")
    if not DB_AVAILABLE:
        print("⚠️ Работаем без сохранения данных (core.memory не найден)")
    
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())