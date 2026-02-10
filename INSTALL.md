# 📦 Установка CNC Assistant

Полная инструкция по установке всех зависимостей проекта.

## 🚀 Быстрая установка

### 1. Клонирование/скачивание проекта
```bash
cd c:\projects\cnc-assistant
```

### 2. Установка базовых зависимостей
```bash
pip install -r requirements.txt
```

### 3. Установка OCR (опционально, для распознавания фотографий)
```bash
pip install -r requirements_ocr.txt
```

### 4. Установка Tesseract OCR (только если нужен OCR)

#### Windows:
1. Скачайте установщик: https://github.com/UB-Mannheim/tesseract/wiki
2. Установите Tesseract OCR
3. **Вариант А:** Добавьте Tesseract в PATH (рекомендуется)
4. **Вариант Б:** Укажите путь в `.env` файле:
```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
```

#### Linux (Fedora):
```bash
sudo dnf install tesseract tesseract-langpack-rus tesseract-langpack-eng
```

#### macOS:
```bash
brew install tesseract tesseract-lang
```

### 5. Настройка переменных окружения
Создайте файл `.env` в корне проекта:
```env
TELEGRAM_TOKEN=ваш_токен_бота_здесь
```

### 6. Запуск проекта
```bash
python app/main.py
```

## 📋 Список зависимостей

### Обязательные зависимости:
- **aiogram** (>=3.0.0) - Telegram Bot Framework
- **sqlalchemy** (>=2.0.0) - ORM для работы с БД
- **python-dotenv** (>=1.0.0) - Загрузка переменных окружения

### Опциональные зависимости (для OCR):
- **pytesseract** (>=0.3.10) - Python обёртка для Tesseract OCR
- **Pillow** (>=10.0.0) - Обработка изображений

### Стандартные библиотеки Python (не требуют установки):
- asyncio, logging, json, re, dataclasses, enum, pathlib, datetime, typing, contextlib, sqlite3, math, decimal, io

## 🔧 Проверка установки

### Проверка Python зависимостей:
```bash
python -c "import aiogram; import sqlalchemy; import dotenv; print('✅ Все зависимости установлены')"
```

### Проверка OCR (если установлен):
```bash
python -c "import pytesseract; from PIL import Image; print('✅ OCR готов к работе')"
```

### Проверка Tesseract OCR:
```bash
tesseract --version
```

## 🐛 Решение проблем

### Проблема: ModuleNotFoundError
**Решение:** Убедитесь, что все зависимости установлены:
```bash
pip install -r requirements.txt --upgrade
```

### Проблема: Tesseract не найден
**Решение:** 
1. Проверьте, что Tesseract установлен: `tesseract --version`
2. Если не работает, укажите путь вручную в `app/core/image_parser.py`

### Проблема: Ошибка импорта aiogram
**Решение:** Установите правильную версию:
```bash
pip install aiogram>=3.0.0
```

### Проблема: База данных не создается
**Решение:** Убедитесь, что есть права на запись в директорию `app/storage/`

## 📝 Минимальная установка (без OCR)

Если не нужна обработка фотографий, можно установить только базовые зависимости:
```bash
pip install aiogram sqlalchemy python-dotenv
```

Проект будет работать, но функция распознавания инструментов с фотографий будет недоступна.

## 🎯 Рекомендуемая версия Python

- **Python 3.10+** (рекомендуется 3.11 или 3.12)

Проверка версии:
```bash
python --version
```

## 📦 Альтернативные способы установки

### Использование venv (рекомендуется):
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### Использование poetry (если настроен):
```bash
poetry install
```

### Использование pipenv (если настроен):
```bash
pipenv install
```

## 🔍 Проверка работоспособности

После установки проверьте:
```bash
# 1. Импорты работают
python -c "from app.core.parser import TextParser; print('✅ Парсер работает')"

# 2. База данных инициализируется
python -c "from app.storage.models import init_orm_database; init_orm_database(); print('✅ БД инициализирована')"

# 3. Knowledge service загружается
python -c "import asyncio; from app.services.knowledge_service import KnowledgeService; asyncio.run(KnowledgeService().initialize()); print('✅ Knowledge service работает')"
```

## 📚 Дополнительная информация

- **requirements.txt** - все основные зависимости
- **requirements_ocr.txt** - зависимости для OCR
- **TOOL_PARSING.md** - документация по парсингу инструментов
- **IMPLEMENTATION.md** - документация по архитектуре
