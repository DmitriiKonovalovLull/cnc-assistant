"""
Улучшенный парсер.
"""

import re


class SimpleParser:
    """Парсер для понимания технических терминов."""

    @staticmethod
    def parse(text):
        text_lower = text.lower().strip()
        result = {}

        # === МАТЕРИАЛЫ ===
        materials = {
            'сталь': 'сталь',
            'сталь 45': 'сталь 45',
            'сталь45': 'сталь 45',
            'алюмин': 'алюминий',
            'титан': 'титан',
            'латун': 'латунь',
            'медь': 'медь',
            'нержавейк': 'нержавейка'
        }

        for key, value in materials.items():
            if key in text_lower:
                result['material'] = value
                break

        # === ОПЕРАЦИИ ===
        if any(word in text_lower for word in ['токар', 'точить', 'проточить']):
            result['operation'] = 'токарная'

        if any(word in text_lower for word in ['фрезер', 'фрез', 'фрезеровк']):
            result['operation'] = 'фрезерная'

        # === РЕЖИМЫ ===
        if any(word in text_lower for word in ['чернов', 'черн', 'груб', 'съем']):
            result['mode'] = 'черновая'

        if any(word in text_lower for word in ['чистов', 'чист', 'финиш', 'точн']):
            result['mode'] = 'чистовая'

        # Если оба режима упомянуты
        if ('черн' in text_lower and 'чист' in text_lower) or \
                ('груб' in text_lower and 'точн' in text_lower):
            result['mode'] = 'оба режима'  # Особый флаг

        # === ДИАМЕТР ===
        # Ищем числа с указанием мм
        mm_patterns = [
            r'(\d+[.,]?\d*)\s*мм',
            r'диаметр\s*(\d+[.,]?\d*)',
            r'[øØ]\s*(\d+[.,]?\d*)',
            r'd\s*(\d+[.,]?\d*)'
        ]

        for pattern in mm_patterns:
            match = re.search(pattern, text_lower)
            if match:
                result['diameter'] = match.group(1)
                break

        # === КОМАНДЫ ===
        command_words = [
            'рекомендац', 'совет', 'подскажи', 'параметр',
            'настрой', 'что делать', 'как', 'помоги',
            'посоветуй', 'скажи', 'дай'
        ]

        for word in command_words:
            if word in text_lower:
                result['command'] = True
                break

        # Короткие команды
        if text_lower in ['дай', 'скажи', 'совет', 'рекомендации']:
            result['command'] = True

        return result