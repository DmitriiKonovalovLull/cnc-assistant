"""
Простой парсер для извлечения сущностей из текста.
Распознает материалы, операции, инструменты, режимы и команды.
"""

import re


class SimpleParser:
    """Парсер ключевых слов."""

    @staticmethod
    def parse(text):
        """Извлекает сущности из текста."""
        text_lower = text.lower().strip()
        result = {}

        # === МАТЕРИАЛЫ ===
        # Точные совпадения
        material_map = {
            'сталь 45': 'сталь 45',
            'сталь45': 'сталь 45',
            'сталь 40х': 'сталь 40х',
            'сталь40х': 'сталь 40х',
            'алюминий': 'алюминий',
            'титан': 'титан',
            'латунь': 'латунь',
            'медь': 'медь',
            'нержавейка': 'нержавейка',
            'нержавеющая': 'нержавейка',
            'чугун': 'чугун'
        }

        for key, value in material_map.items():
            if key in text_lower:
                result['material'] = value
                break

        # Частичные совпадения (если точных не было)
        if 'material' not in result:
            if 'сталь' in text_lower:
                # Извлекаем марку стали
                steel_match = re.search(r'сталь\s*(\d+\w*)', text_lower)
                if steel_match:
                    result['material'] = f"сталь {steel_match.group(1)}"
                else:
                    result['material'] = 'сталь'
            elif 'алюмин' in text_lower:
                result['material'] = 'алюминий'
            elif 'титан' in text_lower:
                result['material'] = 'титан'
            elif 'латун' in text_lower:
                result['material'] = 'латунь'

        # === ОПЕРАЦИИ ===
        if 'токар' in text_lower:
            result['operation'] = 'токарная'
        elif 'фрез' in text_lower:
            result['operation'] = 'фрезерная'
        elif 'сверл' in text_lower:
            result['operation'] = 'сверление'
        elif 'расточ' in text_lower:
            result['operation'] = 'расточка'

        # === ИНСТРУМЕНТЫ ===
        if 'резец' in text_lower:
            result['tool'] = 'резец'
        elif 'фрез' in text_lower:
            result['tool'] = 'фреза'
        elif 'сверл' in text_lower:
            result['tool'] = 'сверло'
        elif 'пластин' in text_lower:
            result['tool'] = 'пластина'

        # === РЕЖИМЫ ===
        if 'черн' in text_lower:
            result['mode'] = 'черновая'
        elif 'чист' in text_lower:
            result['mode'] = 'чистовая'
        elif 'получ' in text_lower:
            result['mode'] = 'получистовая'

        # === КОМАНДЫ ===
        # Человечные команды для рекомендаций
        recommendation_words = [
            'рекомендац', 'совет', 'посоветуй', 'подскажи',
            'что делать', 'как настроить', 'параметр', 'режим',
            'дай совет', 'помоги', 'скажи', 'что ты думаешь'
        ]

        for word in recommendation_words:
            if word in text_lower:
                result['command'] = 'get_recommendations'
                break

        # Команда продолжения
        continue_words = ['да', 'давай', 'го', 'продолж', 'ага', 'угу', 'ок']
        for word in continue_words:
            if word in text_lower and len(text_lower.split()) <= 2:
                result['command'] = 'continue'
                break

        # Специальные запросы
        if text_lower in ['режим', 'какой режим']:
            result['query'] = 'ask_mode'
        elif text_lower in ['инструмент', 'чем работать']:
            result['query'] = 'ask_tool'

        # === КОНКРЕТНЫЕ ПАРАМЕТРЫ ===
        # Диаметр
        diameter_match = re.search(r'диаметр\s*(\d+[.,]?\d*)', text_lower)
        if diameter_match:
            result['diameter'] = diameter_match.group(1)

        # Длина, глубина
        length_match = re.search(r'длин[аойу]\s*(\d+[.,]?\d*)', text_lower)
        if length_match:
            result['length'] = length_match.group(1)

        # Размеры в мм (например: "10 мм", "Ø10")
        mm_match = re.search(r'(?:диаметр\s*)?(\d+[.,]?\d*)\s*(?:мм|mm)', text_lower)
        if mm_match and 'diameter' not in result:
            result['diameter'] = mm_match.group(1)

        # Знак диаметра Ø
        if 'ø' in text_lower or 'Ø' in text:
            dia_match = re.search(r'[øØ]\s*(\d+[.,]?\d*)', text_lower.replace('ø', 'Ø'))
            if dia_match:
                result['diameter'] = dia_match.group(1)

        return result