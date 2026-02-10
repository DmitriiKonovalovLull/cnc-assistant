@echo off
REM Скрипт установки для Windows
REM CNC Assistant - AI-бот для подбора режимов резания

setlocal enabledelayedexpansion

echo 🚀 Установка CNC Assistant...
echo 🧠 AI-бот с пониманием контекста и естественным диалогом
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден. Установите Python 3.10+
    echo    Скачайте с: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python найден
python --version

REM Проверка версии Python
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

if !PYTHON_MAJOR! LSS 3 (
    echo ❌ Требуется Python 3.10+, найдена версия: !PYTHON_VERSION!
    pause
    exit /b 1
)

REM Создание виртуального окружения
if not exist ".venv" (
    if not exist "venv" (
        echo 📦 Создание виртуального окружения...
        python -m venv .venv
        set VENV_DIR=.venv
    ) else (
        set VENV_DIR=venv
    )
) else (
    set VENV_DIR=.venv
)

REM Активация виртуального окружения
echo 🔌 Активация виртуального окружения...
call %VENV_DIR%\Scripts\activate.bat

REM Обновление pip
echo ⬆️ Обновление pip...
python -m pip install --upgrade pip setuptools wheel

REM Установка зависимостей
echo 📥 Установка базовых зависимостей...
pip install -r requirements.txt

REM Установка OCR (опционально)
echo.
set /p install_ocr="Установить OCR для распознавания фотографий инструментов? (y/n): "
if /i "!install_ocr!"=="y" (
    echo 📥 Установка OCR зависимостей...
    pip install -r requirements_ocr.txt
    
    echo.
    echo ⚠️ Не забудьте установить Tesseract OCR:
    echo.
    echo    Скачайте установщик:
    echo    https://github.com/UB-Mannheim/tesseract/wiki
    echo.
    echo    После установки:
    echo    1. Добавьте Tesseract в PATH, или
    echo    2. Укажите путь в app/core/image_parser.py:
    echo       pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    echo.
    echo    Примечание: Бот работает и без OCR, но распознавание
    echo    инструментов с фотографий будет недоступно.
    echo.
)

REM Создание .env файла если нет
if not exist ".env" (
    echo 📝 Создание .env файла...
    (
        echo # Telegram Bot Token
        echo # Получите токен у @BotFather в Telegram
        echo TELEGRAM_TOKEN=ваш_токен_бота_здесь
        echo.
        echo # Опционально: путь к Tesseract OCR (если не в PATH)
        echo # TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
    ) > .env
    echo ⚠️ ВАЖНО: Отредактируйте .env файл и укажите ваш TELEGRAM_TOKEN
    echo    Получить токен: https://t.me/BotFather
)

REM Создание директорий
echo.
echo 📁 Создание необходимых директорий...
if not exist "logs" mkdir logs
if not exist "app\storage" mkdir app\storage
if not exist "app\knowledge\knowledge_base" mkdir app\knowledge\knowledge_base
if not exist "data\rules" mkdir data\rules
if not exist "data\limits" mkdir data\limits
if not exist "training" mkdir training
if not exist "training\datasets" mkdir training\datasets
if not exist "training\prompts" mkdir training\prompts
if not exist "training\finetune" mkdir training\finetune

REM Проверка структуры проекта
echo.
echo 🔍 Проверка структуры проекта...
if not exist "app\main.py" (
    echo ⚠️ Предупреждение: app\main.py не найден
)
if not exist "app\bot\telegram_bot.py" (
    echo ⚠️ Предупреждение: app\bot\telegram_bot.py не найден
)

REM Инициализация базы данных (опционально)
echo.
set /p init_db="Инициализировать базу данных сейчас? (y/n): "
if /i "!init_db!"=="y" (
    echo 🗄️ Инициализация базы данных...
    python -c "from app.storage.models import init_orm_database; from pathlib import Path; import os; db_path = Path('app/storage/cnc.db'); db_path.parent.mkdir(parents=True, exist_ok=True); db_url = f'sqlite:///{str(db_path.absolute()).replace(chr(92), \"/\")}'; init_orm_database(db_url); print('✅ База данных инициализирована')" 2>nul || echo ⚠️ Не удалось инициализировать БД (это нормально, БД создастся при первом запуске)
)

echo.
echo ═══════════════════════════════════════════════════════════
echo ✅ Установка завершена!
echo ═══════════════════════════════════════════════════════════
echo.
echo 📋 Следующие шаги:
echo.
echo 1. Настройте токен бота:
echo    notepad .env
echo    Укажите ваш TELEGRAM_TOKEN
echo.
echo 2. Активируйте виртуальное окружение:
echo    %VENV_DIR%\Scripts\activate.bat
echo.
echo 3. Запустите бота:
echo    python app\main.py
echo.
echo    Или напрямую:
echo    python app\bot\telegram_bot.py
echo.
echo 💡 Особенности бота:
echo    • Естественный диалог без кнопок
echo    • Понимание контекста между сообщениями
echo    • Умные предположения вместо лишних вопросов
echo    • Различение интентов (приветствие, помощь, инженерные запросы)
echo    • Распознавание инструментов с фотографий (если установлен OCR)
echo    • Сохранение и управление работами
echo    • История диалогов и контекста
echo.
echo 📚 Документация:
echo    • INSTALL.md - подробная инструкция по установке
echo    • AI_BOT.md - описание AI-бота
echo    • ARCHITECTURE.md - архитектура системы
echo    • ARCHITECTURE_FINAL.md - финальная архитектура
echo    • SCALABILITY.md - масштабируемость и LLM готовность
echo.
pause
