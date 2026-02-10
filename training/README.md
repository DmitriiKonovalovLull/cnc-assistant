# 🎓 Training Data

Директория для данных обучения LLM.

## Структура

- `datasets/` - JSONL файлы с данными для обучения
- `prompts/` - Системные промпты для LLM
- `finetune/` - Скрипты и конфигурация для fine-tuning

## Форматы данных

### ChatML формат
```json
{
  "messages": [
    {"role": "user", "content": "Материал: титан, диаметры: Ø200→50"},
    {"role": "assistant", "content": "Скорость резания: 30 м/мин..."}
  ]
}
```

### Alpaca формат
```json
{
  "instruction": "Подбери режимы резания",
  "input": "Материал: титан...",
  "output": "Скорость резания: 30 м/мин..."
}
```

## Генерация датасета

```python
from app.storage.data_pipeline import DataPipeline
from app.storage.models import get_session

session = get_session()
pipeline = DataPipeline(session)
dataset_file = pipeline.prepare_dataset(format_type="chatml")
```

## Использование для обучения

Данные готовы для:
- Fine-tuning локальных моделей (Llama, Mistral)
- Дообучения через API (OpenAI, Anthropic)
- RAG (Retrieval Augmented Generation)
- Обучения собственной LLM
