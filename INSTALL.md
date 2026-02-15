# Установка CNC Assistant

Проще всего — запустить скрипт установки. Он создаст venv, обновит pip и поставит зависимости.

**Windows:** `setup.bat`  
**Linux/macOS:** `chmod +x setup.sh && ./setup.sh`

Скрипт спросит, ставить ли OCR (распознавание фото инструментов) и инициализировать ли БД. В конце нужно указать в `.env` токен бота (получить у [@BotFather](https://t.me/BotFather)).

---

## Ручная установка

Если ставишь вручную — используй pip из виртуального окружения (`python -m pip`), чтобы не смешивать с системным Python.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/mac:  source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Создай в корне проекта файл `.env` с токеном:
```env
TELEGRAM_TOKEN=ваш_токен_здесь
```

Запуск: `python app/main.py` или `python app/bot/telegram_bot.py`.

---

## OCR (распознавание инструментов с фото)

Нужны Tesseract и Python-пакеты:

- **Tesseract:** [скачать для Windows](https://github.com/UB-Mannheim/tesseract/wiki), на Linux: `sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng`, на macOS: `brew install tesseract tesseract-lang`
- В `.env` можно указать путь, если Tesseract не в PATH:  
  `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
- Пакеты: `python -m pip install -r requirements_ocr.txt`

Без OCR бот работает, но не будет распознавать инструмент по фото.

---

## Поиск по интернету (Sandvik, Kennametal и др.)

Для умного парсера SPA-сайтов (см. [INTERNET_SEARCH.md](INTERNET_SEARCH.md)):

```bash
python -m pip install -r requirements_internet.txt
playwright install
```

Без этого поиск в интернете будет через обычные запросы (часть сайтов может отдавать пустые страницы).

---

## Проблемы

- **ModuleNotFoundError** — убедись, что активирован venv и зависимости стоят: `python -m pip install -r requirements.txt`
- **Tesseract не найден** — установи Tesseract и при необходимости укажи `TESSERACT_CMD` в `.env`
- **БД не создаётся** — проверь права на запись в `app/storage/`

Требуется Python 3.10+.
