#!/bin/bash
# Скрипт установки для Linux/macOS
# CNC Assistant - AI-бот для подбора режимов резания

set -e  # Остановка при ошибках

echo "🚀 Установка CNC Assistant..."
echo "🧠 AI-бот с пониманием контекста и естественным диалогом"
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Установите Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo "❌ Требуется Python 3.10+, найдена версия: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python версия: $PYTHON_VERSION"

# Создание виртуального окружения
if [ ! -d ".venv" ] && [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv .venv
    VENV_DIR=".venv"
elif [ -d ".venv" ]; then
    VENV_DIR=".venv"
else
    VENV_DIR="venv"
fi

# Активация виртуального окружения
echo "🔌 Активация виртуального окружения..."
source $VENV_DIR/bin/activate

# Обновление pip
echo "⬆️ Обновление pip..."
pip install --upgrade pip setuptools wheel

# Установка зависимостей
echo "📥 Установка базовых зависимостей..."
pip install -r requirements.txt

# Установка OCR (опционально)
echo ""
read -p "Установить OCR для распознавания фотографий инструментов? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📥 Установка OCR зависимостей..."
    pip install -r requirements_ocr.txt
    
    # Проверка Tesseract
    if ! command -v tesseract &> /dev/null; then
        echo ""
        echo "⚠️ Tesseract OCR не найден в системе."
        echo "Установите его:"
        echo ""
        echo "  Ubuntu/Debian:"
        echo "    sudo apt-get update"
        echo "    sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng"
        echo ""
        echo "  Fedora/RHEL:"
        echo "    sudo dnf install tesseract tesseract-langpack-rus tesseract-langpack-eng"
        echo ""
        echo "  macOS:"
        echo "    brew install tesseract tesseract-lang"
        echo ""
        echo "  Arch Linux:"
        echo "    sudo pacman -S tesseract tesseract-data-rus tesseract-data-eng"
        echo ""
        echo "  Примечание: Бот работает и без OCR, но распознавание"
        echo "  инструментов с фотографий будет недоступно."
        echo ""
    else
        TESSERACT_VERSION=$(tesseract --version 2>&1 | head -n1)
        echo "✅ Tesseract OCR найден: $TESSERACT_VERSION"
    fi
fi

# Создание .env файла если нет
if [ ! -f ".env" ]; then
    echo ""
    echo "📝 Создание .env файла..."
    cat > .env << EOF
# Telegram Bot Token
# Получите токен у @BotFather в Telegram
TELEGRAM_TOKEN=ваш_токен_бота_здесь

# Опционально: путь к Tesseract OCR (если не в PATH)
# TESSERACT_CMD=/usr/bin/tesseract
EOF
    echo "⚠️ ВАЖНО: Отредактируйте .env файл и укажите ваш TELEGRAM_TOKEN"
    echo "   Получить токен: https://t.me/BotFather"
fi

# Создание директорий
echo ""
echo "📁 Создание необходимых директорий..."
mkdir -p logs
mkdir -p app/storage
mkdir -p app/knowledge/knowledge_base
mkdir -p data/rules
mkdir -p data/limits
mkdir -p training/datasets
mkdir -p training/prompts
mkdir -p training/finetune

# Проверка структуры проекта
echo ""
echo "🔍 Проверка структуры проекта..."
if [ ! -f "app/main.py" ]; then
    echo "⚠️ Предупреждение: app/main.py не найден"
fi

if [ ! -f "app/bot/telegram_bot.py" ]; then
    echo "⚠️ Предупреждение: app/bot/telegram_bot.py не найден"
fi

# Инициализация базы данных (опционально)
echo ""
read -p "Инициализировать базу данных сейчас? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗄️ Инициализация базы данных..."
    python3 -c "
from app.storage.models import init_orm_database
from pathlib import Path
import os
db_path = Path('app/storage/cnc.db')
db_path.parent.mkdir(parents=True, exist_ok=True)
db_url = f'sqlite:///{db_path.absolute().as_posix()}'
init_orm_database(db_url)
print('✅ База данных инициализирована')
" || echo "⚠️ Не удалось инициализировать БД (это нормально, БД создастся при первом запуске)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Установка завершена!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📋 Следующие шаги:"
echo ""
echo "1. Настройте токен бота:"
echo "   nano .env  # или другой редактор"
echo "   Укажите ваш TELEGRAM_TOKEN"
echo ""
echo "2. Активируйте виртуальное окружение:"
echo "   source $VENV_DIR/bin/activate"
echo ""
echo "3. Запустите бота:"
echo "   python app/main.py"
echo ""
echo "   Или напрямую:"
echo "   python app/bot/telegram_bot.py"
echo ""
echo "💡 Особенности бота:"
echo "   • Естественный диалог без кнопок"
echo "   • Понимание контекста между сообщениями"
echo "   • Умные предположения вместо лишних вопросов"
echo "   • Различение интентов (приветствие, помощь, инженерные запросы)"
echo "   • Распознавание инструментов с фотографий (если установлен OCR)"
echo "   • Сохранение и управление работами"
echo "   • История диалогов и контекста"
echo ""
echo "📚 Документация:"
echo "   • INSTALL.md - подробная инструкция по установке"
echo "   • AI_BOT.md - описание AI-бота"
echo "   • ARCHITECTURE.md - архитектура системы"
echo "   • ARCHITECTURE_FINAL.md - финальная архитектура"
echo "   • SCALABILITY.md - масштабируемость и LLM готовность"
echo ""
