"""
Очистка извлечённого текста: нормализация пробелов, переносов, чисел.
Парсер не принимает решений — только подготавливает сырьё.
"""

import re
from typing import List


def normalize_whitespace(text: str) -> str:
    """Свести последовательности пробелов/переносов к одному пробелу."""
    if not text:
        return ""
    return re.sub(r"[\s\u00a0]+", " ", text).strip()


def normalize_number_delimiter(text: str, decimal: str = ".", thousands: str = "") -> str:
    """Нормализовать разделитель десятичных (запятая → точка)."""
    if not text:
        return ""
    return text.replace(",", decimal).replace("\u202f", "").replace(" ", thousands)


def split_into_lines(text: str) -> List[str]:
    """Разбить текст на строки, убрать пустые."""
    if not text:
        return []
    return [normalize_whitespace(s) for s in text.splitlines() if normalize_whitespace(s)]


def extract_possible_numbers(text: str) -> List[float]:
    """Извлечь из строки все числа (целые и с десятичной точкой/запятой)."""
    if not text:
        return []
    normalized = normalize_number_delimiter(text)
    pattern = re.compile(r"-?\d+(?:[.,]\d+)?")
    out = []
    for m in pattern.finditer(normalized):
        try:
            out.append(float(m.group().replace(",", ".")))
        except ValueError:
            continue
    return out
