# CNC Assistant 🏭🤖

CNC Assistant is an AI-like industrial assistant for CNC operators.

It does not just calculate cutting modes —  
it reasons, makes assumptions, remembers users, and learns from corrections.

---

## ✨ What makes it different?

✅ **Natural dialogue** - No buttons, just text like talking to a human  
✅ **Context understanding** - Remembers what you said between messages  
✅ **Smart assumptions** - Makes intelligent guesses instead of asking everything  
✅ **Never asks twice** - Remembers material, operation, tool, diameter  
✅ **Explains reasoning** - Shows *why* a mode was chosen  
✅ **Learns from feedback** - Collects real operator experience  
✅ **Image recognition** - Recognizes tools from photos (with OCR)  
✅ **Designed for LLM** - Ready to evolve into a full LLM-based system  

---

## 🧠 How it works (short)

1. **User writes naturally** (no buttons!):
   > "Сталь, токарный ЧПУ, снять с Ø100 до Ø90"
   > "Алюминий, черновая обработка, станок 11 кВт"
   > [sends photo of tool] → "Теперь обработай эту деталь"

2. **Assistant**:
   - Parses intent from free-form text
   - Updates context (remembers between messages)
   - Makes smart assumptions if data is missing
   - Recognizes tools from photos (with OCR)
   - Chooses the next logical step

3. **Outputs**:
   - Recommendation with explanation
   - Shows what was assumed and why
   - Asks for your real-world parameters

4. **Your feedback** is saved as training data for future LLM.

---

## 🔁 Dialog logic

**Natural conversation** - no buttons, no forms, just talk.

❌ Old way: Click buttons → Fill forms → Answer questions  
✅ New way: Describe task → Get recommendation → Share your experience

**Example dialog:**
```
You: Сталь, токарный ЧПУ, снять с Ø100 до Ø90

Bot: ✅ Понял:
👤 Материал: сталь
👤 Диаметры: Ø100 → Ø90 мм
🤖 Станок: токарный ЧПУ (предположено)
🤖 Режим: черновая (предположено на основе припуска)

🎯 РЕКОМЕНДУЮ:
⚡ Скорость резания: 150 м/мин
🔄 Обороты: 477 об/мин
...

💬 Какие параметры вы используете на практике?
```

---

## 🧩 Architecture

- **Transport layer**: Telegram / CLI / Web
- **Dialog Manager**: FSM with `active_step`
- **Context**: per-user memory (единый объект состояния)
- **Parser**: извлечение данных из текста и изображений
- **Assumptions Engine**: разумные предположения
- **Knowledge Service**: база знаний материалов, инструментов, станков
- **Rule Engine**: YAML-based cutting modes
- **Feedback Loop**: creates future dataset

LLM is **not required** to start.

---

## 📦 Установка

### 🚀 Автоматическая установка (рекомендуется):

**Windows:**
```bash
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

Скрипт автоматически:
- ✅ Проверит версию Python (требуется 3.10+)
- ✅ Создаст виртуальное окружение
- ✅ Установит все зависимости
- ✅ Создаст необходимые директории
- ✅ Настроит .env файл
- ✅ Опционально установит OCR для распознавания фотографий

### 📝 Ручная установка:

```bash
# 1. Создайте виртуальное окружение
python -m venv .venv

# 2. Активируйте его
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Опционально: OCR для распознавания фотографий
pip install -r requirements_ocr.txt

# 5. Создайте .env файл с токеном бота
echo "TELEGRAM_TOKEN=ваш_токен" > .env

# 6. Запуск
python app/main.py
```

📚 Подробная инструкция: [INSTALL.md](INSTALL.md)

### Зависимости:

- **aiogram** (>=3.0.0) - Telegram Bot Framework
- **sqlalchemy** (>=2.0.0) - ORM для БД
- **python-dotenv** (>=1.0.0) - Загрузка .env
- **pytesseract** (опционально) - OCR для фотографий
- **Pillow** (опционально) - Обработка изображений

Полный список: [requirements.txt](requirements.txt)

---

## 📊 Data for learning

All dialogs and corrections are stored in JSONL:

- `data/logs/dialogs.jsonl`
- `data/logs/corrections.jsonl`

This data will be used to train a future CNC-specific LLM.

---

## 🚀 Roadmap

- [x] Rule-based AI behavior
- [x] Persistent user memory
- [x] Feedback-based learning
- [ ] Ranking rules by operator corrections
- [ ] Hybrid (Rules + Small LLM)
- [ ] Full CNC LLM fine-tuned on real dialogs

---

## ⚠️ Disclaimer

This assistant provides recommendations.
Always verify parameters according to your machine, tool, and safety rules.

---

## 👨‍🏭 Who is it for?

- CNC operators
- Technologists
- Setup specialists
- CNC learners

---

## 💬 Philosophy

> The assistant should behave like a calm,
> experienced machinist standing next to you —
> not like a calculator or a form.

---

