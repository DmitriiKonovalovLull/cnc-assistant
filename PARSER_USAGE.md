# 📋 Руководство по использованию парсеров

## Обзор

Система парсеров для поиска инструментов, деталей, чертежей и станков состоит из трех основных компонентов:

1. **TextParser** - парсинг текста пользователя
2. **ImageParser** - распознавание инструментов с фотографий
3. **DrawingParser** - парсинг технических чертежей
4. **UniversalParser** - универсальный парсер, объединяющий все возможности

## 🚀 Быстрый старт

### Универсальный парсер (рекомендуется)

```python
from app.core.universal_parser import UniversalParser

# Инициализация
parser = UniversalParser(tesseract_cmd=None)  # Использует системный PATH

# Парсинг текста
result = parser.parse(text="CNMG 120408 твердый сплав, станок Gamma 1250")

# Парсинг изображения инструмента
with open("tool_photo.jpg", "rb") as f:
    image_data = f.read()
result = parser.parse(image_data=image_data, is_drawing=False)

# Парсинг чертежа
with open("drawing.png", "rb") as f:
    image_data = f.read()
result = parser.parse(image_data=image_data, is_drawing=True)

# Результат содержит:
# - tools: список найденных инструментов
# - parts: список найденных деталей
# - machines: список найденных станков
# - text_data: данные из текстового парсинга
# - image_data: данные из парсинга изображения
# - drawing_data: данные из парсинга чертежа
```

## 📝 Примеры использования

### 1. Поиск инструментов в тексте

```python
from app.core.universal_parser import UniversalParser

parser = UniversalParser()

# Поиск инструментов
tools = parser.search_tools("CNMG 120408 от Sandvik, марка GC1020")
# Результат:
# [
#   {
#     'name': 'CNMG 120408',
#     'material': 'твердый сплав',
#     'manufacturer': 'SANDVIK',
#     'grade': 'GC1020',
#     'source': 'text',
#     'confidence': 0.85
#   }
# ]
```

### 2. Поиск деталей в тексте

```python
parts = parser.search_parts("болт ГОСТ 7798-30, сталь 40Х, диаметр 20мм, длина 50мм")
# Результат:
# [
#   {
#     'material': '40Х',
#     'diameter_start': 20.0,
#     'length': 50.0,
#     'source': 'text',
#     'confidence': 0.9
#   }
# ]
```

### 3. Поиск станков в тексте

```python
machines = parser.search_machines("работаю на токарном ЧПУ Gamma 1250 tc, мощность 15 кВт")
# Результат:
# [
#   {
#     'type': 'Gamma 1250 tc',
#     'power': 15.0,
#     'source': 'text',
#     'confidence': 0.8
#   }
# ]
```

### 4. Парсинг чертежа

```python
with open("drawing.png", "rb") as f:
    image_data = f.read()

drawing_info = parser.parse_drawing_image(image_data)
# Результат:
# {
#   'part_name': 'Болт',
#   'part_number': 'Б-001',
#   'standard': 'ГОСТ 7798-30',
#   'material': '40Х',
#   'diameters': [20.0],
#   'lengths': [50.0],
#   'tolerances': {'IT7': 0.0},
#   'surface_roughness': 'Ra 3.2',
#   'operations': ['токарная'],
#   'confidence': 0.85
# }
```

## 🔧 Компоненты парсеров

### TextParser

Парсит текст и извлекает:
- Материалы (сталь, алюминий, нержавейка и т.д.)
- Операции (токарка, фрезерование, сверление)
- Режимы обработки (черновая, чистовая)
- Размеры (диаметры, длины)
- Инструменты (ISO коды, производители, марки)
- Станки (типы, мощность, названия моделей)
- Параметры режимов (обороты, подачи, глубина резания)

### ImageParser

Распознает инструменты с фотографий:
- ISO коды инструментов (CNMG, WNMG и т.д.)
- Производителей (Sandvik, Kennametal и т.д.)
- Марки/градации (GC1020, P25 и т.д.)
- Радиусы пластин
- Материалы инструментов

### DrawingParser

Извлекает информацию из технических чертежей:
- Название детали
- Номер детали
- Стандарты (ГОСТ, ОСТ, DIN, ISO)
- Размеры (диаметры, длины, ширины, высоты)
- Допуски (IT7, H7, h6, ±0.1)
- Шероховатость (Ra 1.6, Ra 3.2)
- Материалы
- Операции обработки

## 📊 Структура результатов

### Результат UniversalParser.parse()

```python
{
    'success': True,  # Успешность парсинга
    'text_data': {...},  # Данные из TextParser
    'image_data': {...},  # Данные из ImageParser
    'drawing_data': {...},  # Данные из DrawingParser
    'tools': [...],  # Список найденных инструментов
    'parts': [...],  # Список найденных деталей
    'machines': [...],  # Список найденных станков
    'confidence': 0.85  # Общая уверенность парсинга
}
```

### Структура инструмента

```python
{
    'name': 'CNMG 120408',  # ISO код
    'type': 'токарный проходной (ромбическая 80°)',
    'material': 'carbide',  # Материал инструмента
    'grade': 'GC1020',  # Марка/градация
    'radius': 0.8,  # Радиус пластины (мм)
    'manufacturer': 'SANDVIK',  # Производитель
    'source': 'text' | 'image',  # Источник данных
    'confidence': 0.85  # Уверенность распознавания
}
```

### Структура детали

```python
{
    'name': 'Болт',  # Название детали
    'part_number': 'Б-001',  # Номер детали
    'standard': 'ГОСТ 7798-30',  # Стандарт
    'material': '40Х',  # Материал
    'diameters': [20.0],  # Диаметры (мм)
    'lengths': [50.0],  # Длины (мм)
    'tolerances': {'IT7': 0.0},  # Допуски
    'surface_roughness': 'Ra 3.2',  # Шероховатость
    'operations': ['токарная'],  # Операции обработки
    'source': 'text' | 'drawing',  # Источник данных
    'confidence': 0.85  # Уверенность распознавания
}
```

### Структура станка

```python
{
    'type': 'Gamma 1250 tc',  # Тип/модель станка
    'power': 15.0,  # Мощность (кВт)
    'source': 'text',  # Источник данных
    'confidence': 0.8  # Уверенность распознавания
}
```

## ⚙️ Настройка

### Настройка Tesseract OCR

Для работы с изображениями и чертежами требуется Tesseract OCR:

**Windows:**
```bash
# Скачать с https://github.com/UB-Mannheim/tesseract/wiki
# Установить и добавить в PATH
# Или указать путь в .env:
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

### Установка зависимостей

```bash
# Базовые зависимости
pip install -r requirements.txt

# С OCR (для изображений и чертежей)
pip install -r requirements_ocr.txt
```

## 🎯 Примеры запросов

### Поиск инструментов

```python
# По ISO коду
tools = parser.search_tools("CNMG 120408")

# По производителю и марке
tools = parser.search_tools("Sandvik GC1020")

# По материалу
tools = parser.search_tools("твердый сплав радиус 0.8")
```

### Поиск деталей

```python
# По стандарту
parts = parser.search_parts("ГОСТ 7798-30")

# По материалу и размерам
parts = parser.search_parts("сталь 40Х диаметр 20 длина 50")

# По описанию
parts = parser.search_parts("болт с шестигранной головкой")
```

### Поиск станков

```python
# По модели
machines = parser.search_machines("Gamma 1250 tc")

# По типу и мощности
machines = parser.search_machines("токарный ЧПУ 15 кВт")

# По описанию
machines = parser.search_machines("работаю на токарном станке с ЧПУ")
```

## 🔍 Расширенные возможности

### Комбинированный парсинг

```python
# Парсинг текста и изображения одновременно
result = parser.parse(
    text="CNMG 120408 от Sandvik",
    image_data=image_bytes,
    is_drawing=False
)

# Результат содержит данные из обоих источников
tools_from_text = result['tools']  # Инструменты из текста
tools_from_image = [t for t in result['tools'] if t['source'] == 'image']  # Инструменты с фото
```

### Парсинг чертежа с текстовым описанием

```python
result = parser.parse(
    text="Болт по ГОСТ 7798-30",
    image_data=drawing_bytes,
    is_drawing=True
)

# Объединенные данные о детали
parts = result['parts']  # Данные из текста и чертежа
```

## 📝 Примечания

1. **OCR точность**: Точность распознавания зависит от качества изображения. Рекомендуется использовать четкие фотографии с хорошим освещением.

2. **Поддержка языков**: Tesseract должен быть настроен для русского и английского языков.

3. **Производительность**: Парсинг изображений занимает больше времени, чем парсинг текста. Для больших объемов рекомендуется использовать асинхронную обработку.

4. **Расширяемость**: Все парсеры можно расширить, добавив новые паттерны распознавания в соответствующие классы.
