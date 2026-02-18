# CNC Assistant

## Быстрый старт

### Интерактивный CLI для работы со стандартами

Запустите `main.py` для интерактивной работы со всеми мировыми системами стандартов:

```bash
python main.py
```

**Возможности:**
- Поддержка всех мировых систем стандартов (ГОСТ, ISO, DIN, GB, JIS, ANSI, BS)
- Автоопределение системы по обозначению
- Поиск аналогов стандартов в других системах с процентами совпадения
- Региональные настройки (RU, CN, EU, US, JP, GB, GLOBAL)
- Интерактивный режим с меню выбора

**Пример использования:**
```
Выберите систему стандартов:
  1. ГОСТ (Россия/СНГ)
  2. ISO (международный)
  ...
  8. Автоопределение

Введите обозначение: M20

📊 Аналоги стандарта M20 (ISO):
  GOST   24705          [████████████████████] 100%
  DIN    13-1           [████████████████████] 100%
  GB     192            [██████████████████░░]  98%
```

---

AI-like industrial assistant for CNC operators: cutting modes, context, assumptions, and learning from feedback.

---

## Features

- **Languages** — interface in Russian, English, Chinese (`/lang` to switch)
- **Natural dialogue** — describe the task in text, get recommendations with reasoning
- **Context** — remembers material, operation, tool, diameters between messages
- **Assumptions** — fills missing data with sensible defaults
- **Tool recognition** — OCR from photos (Tesseract)
- **Internet search** — looks up tools and machines online
- **Drawing parsing** — extracts data from technical drawings
- **Standards** — GOST, OST, DIN, ISO
- **Engineering module** — full cutting calculation with power/torque/vibration risk
- **Vibration analysis** — from spectrum photo or entered frequency (tooth/imbalance/resonance)
- **Machine learning** — adapts K_machine and stable zones from operation history

---

## Quick start

**Windows:** `setup.bat`  
**Linux/macOS:** `chmod +x setup.sh && ./setup.sh`

### Запуск через main.py (рекомендуется)

Главная точка входа с проверкой целостности проекта и автозагрузкой стандартов:

```bash
python main.py
```

**Возможности main.py:**
- ✅ Автоматическая проверка структуры проекта
- ✅ Проверка установленных зависимостей
- ✅ Проверка наличия .env файла и токена
- ✅ **Автозагрузка стандартов** (ГОСТ, ОСТ, ISO, DIN, GB, JIS, ANSI, BS) при старте
- ✅ **Автоматический запуск бота** если токен найден
- ✅ Меню настройки (если токен не найден):
  - Запуск Telegram бота
  - Проверка целостности проекта
  - Установка зависимостей

**Автозагрузка стандартов:**
При запуске `main.py` автоматически загружаются:
- ГОСТ резьбы и допуски
- ISO допуски и резьбы
- Реестр стандартов (WorldStandardRegistry)
- Движок эквивалентности стандартов
- База данных эквивалентности

Стандарты интегрированы в логику Telegram бота - бот автоматически распознает обозначения стандартов (M20, H7, Ra 1.6 и т.д.) и предоставляет информацию о них.

**Математические вычисления:**
Все вычисления выполняются строго по формулам ISO/GOST:
- Геометрия резьбы (ISO 965-1)
- IT допуски (ISO 286)
- Посадки (зазоры/натяги)
- Шероховатость (связь с подачей)

**Тестирование:**
```bash
# Запуск тестов через main.py (пункт 5)
python main.py

# Или напрямую
pytest tests/standards -v
```

**Обновление стандартов:**
```bash
# Через main.py (пункт 4)
python main.py

# Или напрямую
python standards/cli/update_standards.py update-standards
```

### Прямой запуск компонентов

**Telegram бот:**
```bash
python app/bot/telegram_bot.py
```

**CLI режим:**
```bash
python app/bot/cli_bot.py
```

**Установка зависимостей:**
```bash
pip install -r requirements.txt
```

**Настройка .env:**
Создайте файл `.env` в корне проекта:
```
TELEGRAM_TOKEN=ваш_токен_бота
```

Details: [INSTALL.md](INSTALL.md).

---

## Architecture

| Layer | Description |
|-------|-------------|
| Transport | Telegram / CLI |
| Context | Per-user state (material, tool, machine, diameters) |
| Parser | Text + image (OCR) + drawings |
| Knowledge | Materials, tools, machines, standards |
| Engineering | `calculate_optimal_modes`, power/torque/risk, modes (AGGRESSIVE/NORMAL/SAFE) |
| Vibration | `analyze_vibration` / from image; tooth / imbalance / resonance + corrections |
| Learning | `record_operation`, `update_machine_learning`, safe zones, K_machine_real |
| Selector | `select_best_machine` by power, torque, rigidity, score formula |

Main entry points:

- **calculate_optimal_modes** — `app/services/engineering_calculator.py`
- **analyze_vibration** — `app/services/vibration_analyzer.py`
- **update_machine_learning** — `app/services/machine_learning_service.py`
- **select_best_machine** — `app/services/machine_selector.py`

Coefficients and thresholds are in DB (`calculation_coefficients`). Machine data: [docs/MACHINES_DATABASE.md](docs/MACHINES_DATABASE.md).

---

## Data and learning

- Dialogs and corrections: `data/logs/dialogs.jsonl`, `data/logs/corrections.jsonl`
- Machine history: `machine_operation_history`, `machine_learned_params` (see schema in `app/storage/schema_machines_postgres.sql`)

---

## Dependencies

- **Core:** [requirements.txt](requirements.txt)
- **OCR (photos):** [requirements_ocr.txt](requirements_ocr.txt) + Tesseract
- **Internet (SPA):** [requirements_internet.txt](requirements_internet.txt) + `playwright install`
- **CI / lint:** [requirements-dev.txt](requirements-dev.txt) (includes ruff)

---

## Disclaimer

Recommendations only. Always check parameters against your machine, tool, and safety rules.
