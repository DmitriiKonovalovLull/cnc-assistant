# CNC Assistant

AI-like industrial assistant for CNC operators: cutting modes, context, assumptions, and learning from feedback.

---

## Features

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

Then set `TELEGRAM_TOKEN` in `.env` and run:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
python app/bot/telegram_bot.py
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
