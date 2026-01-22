"""
Парсер намерений пользователя без LLM.
Определяет, что хочет пользователь.
"""
import re
from typing import Dict, Any, Optional


def parse_intent(text: str) -> Dict[str, Any]:
    """
    Парсит текст и определяет намерение.
    Пока простой rule-based.
    """
    text_lower = text.lower()

    # Проверяем, хочет ли пользователь начать заново
    if any(word in text_lower for word in ['заново', 'сначала', 'новый', 'ещё']):
        return {'intent': 'restart'}

    # Проверяем, хочет ли пользователь помощь
    if any(word in text_lower for word in ['помощь', 'help', 'справка']):
        return {'intent': 'help'}

    # Проверяем, это число (обороты)
    if re.match(r'^\d+(\.\d+)?$', text):
        return {'intent': 'number_input', 'value': float(text)}

    # По умолчанию считаем текстовым вводом
    return {'intent': 'text_input', 'value': text}


def extract_material(text: str) -> Optional[str]:
    """Извлекает материал из текста."""
    materials = {
        'сталь': ['сталь', 'steel', 'стали'],
        'алюминий': ['алюмин', 'aluminum', 'ал'],
        'титан': ['титан', 'titanium', 'тита'],
        'нержавейка': ['нерж', 'stainless', 'коррозион'],
        'чугун': ['чугун', 'cast iron', 'чугу'],
        'латунь': ['латунь', 'brass', 'лату'],
        'медь': ['медь', 'copper', 'мед'],
        'бронза': ['бронз', 'bronze'],
    }

    text_lower = text.lower()
    for material, keywords in materials.items():
        if any(keyword in text_lower for keyword in keywords):
            return material

    return None


def extract_diameter(text: str) -> Optional[float]:
    """Извлекает диаметр из текста."""
    patterns = [
        r'(\d+(?:[.,]\d+)?)\s*мм',
        r'диаметр\s*(\d+(?:[.,]\d+)?)',
        r'Ø\s*(\d+(?:[.,]\d+)?)',
        r'(\d+(?:[.,]\d+)?)\s*diam',
    ]

    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                continue

    return None