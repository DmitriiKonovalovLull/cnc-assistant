"""
Парсер сообщений.
"""

import re


class SimpleParser:
    """Парсер ключевых слов."""

    @staticmethod
    def parse(text):
        text_lower = text.lower().strip()
        result = {}

        # Материалы
        if 'сталь' in text_lower:
            result['material'] = 'сталь'
            steel_match = re.search(r'сталь\s*(\d+\w*)', text_lower)
            if steel_match:
                result['material'] = f"сталь {steel_match.group(1)}"

        elif 'алюмин' in text_lower:
            result['material'] = 'алюминий'

        elif 'титан' in text_lower:
            result['material'] = 'титан'

        # Операции
        if 'токар' in text_lower:
            result['operation'] = 'токарная'
        elif 'фрез' in text_lower:
            result['operation'] = 'фрезерная'

        # Режимы
        if 'черн' in text_lower:
            result['mode'] = 'черновая'
        elif 'чист' in text_lower:
            result['mode'] = 'чистовая'

        # Диаметр
        dia_match = re.search(r'(\d+[.,]?\d*)\s*(?:мм|mm|Ø|ø|диаметр)', text_lower)
        if dia_match:
            result['diameter'] = dia_match.group(1)

        # Команды рекомендаций
        command_words = [
            'рекомендац', 'совет', 'подскажи', 'параметр',
            'режимы', 'настрой', 'что делать', 'как', 'помоги',
            'посоветуй', 'скажи'
        ]

        for word in command_words:
            if word in text_lower:
                result['command'] = 'get_recommendations'
                break

        # "дай" только если не просто "да"
        if 'дай' in text_lower and len(text_lower) > 3:
            result['command'] = 'get_recommendations'

        # Положительные ответы (НЕ команды)
        positive_words = ['да', 'ок', 'хорошо', 'ага', 'угу', 'ладно', 'понял', 'ясно']
        if text_lower in positive_words:
            result['response'] = 'positive'

        return result