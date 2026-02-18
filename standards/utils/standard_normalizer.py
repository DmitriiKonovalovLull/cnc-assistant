"""
Нормализация номеров стандартов.
Приводит различные форматы к единому виду для поиска.
"""

import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def normalize_standard_text(text: str) -> str:
    """
    Нормализовать текст стандарта для поиска.
    
    Приводит к единому формату:
    - Убирает лишние пробелы
    - Заменяет разные типы дефисов на стандартный
    - Приводит к верхнему регистру
    
    Args:
        text: Текст стандарта (например "ОСТ 33080-80", "ОСТ33080–80")
        
    Returns:
        Нормализованный текст
    """
    if not text:
        return ""
    
    # Приводим к верхнему регистру
    text = text.upper().strip()
    
    # Заменяем разные типы дефисов и тире на стандартный дефис
    # Unicode дефисы: – (U+2013), — (U+2014), ― (U+2015)
    text = text.replace('–', '-')  # EN DASH
    text = text.replace('—', '-')  # EM DASH
    text = text.replace('―', '-')  # HORIZONTAL BAR
    
    # Убираем лишние пробелы вокруг дефисов
    text = re.sub(r'\s*-\s*', '-', text)
    
    # Нормализуем пробелы (множественные -> один)
    text = re.sub(r'\s+', ' ', text)
    
    # Убираем пробелы вокруг стандартного типа
    text = re.sub(r'\s*(ГОСТ|ОСТ|OST|DIN|ISO)\s*', r'\1 ', text)
    
    return text.strip()


def parse_standard_designation(text: str) -> Optional[Dict[str, str]]:
    """
    Распарсить обозначение стандарта.
    
    Поддерживает форматы:
    - ГОСТ 7798-30
    - ОСТ 33080-80
    - ОСТ 1 33056-80
    - DIN 912
    - ISO 4014
    
    Args:
        text: Текст с обозначением стандарта
        
    Returns:
        Словарь с type, number, year или None
    """
    if not text:
        return None
    
    # Нормализуем текст
    normalized = normalize_standard_text(text)
    
    # Паттерны для разных форматов
    patterns = [
        # ОСТ с префиксом: "ОСТ 1 33056-80"
        r'(ОСТ|OST)\s+(\d+)\s+(\d{5})-(\d{2})',
        # ГОСТ/ОСТ с дефисом: "ГОСТ 7798-30", "ОСТ 33080-80"
        r'(ГОСТ|ОСТ|OST|DIN|ISO)\s+(\d+)-(\d{2})',
        # ГОСТ/ОСТ без года: "DIN 912", "ISO 4014"
        r'(ГОСТ|ОСТ|OST|DIN|ISO)\s+(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            standard_type = match.group(1).upper()
            # Нормализуем ОСТ -> OST для единообразия
            if standard_type == 'ОСТ':
                standard_type = 'OST'
            
            if len(match.groups()) == 4:
                # Формат "ОСТ 1 33056-80"
                prefix = match.group(2)
                number = match.group(3)
                year = match.group(4)
                return {
                    'type': standard_type,
                    'prefix': prefix,
                    'number': number,
                    'year': year,
                    'full_number': f"{prefix} {number}-{year}"
                }
            elif len(match.groups()) == 3:
                # Формат "ГОСТ 7798-30"
                number = match.group(2)
                year = match.group(3)
                return {
                    'type': standard_type,
                    'number': number,
                    'year': year,
                    'full_number': f"{number}-{year}"
                }
            elif len(match.groups()) == 2:
                # Формат "DIN 912"
                number = match.group(2)
                return {
                    'type': standard_type,
                    'number': number,
                    'full_number': number
                }
    
    return None


def normalize_standard_number(standard_type: str, standard_number: str) -> str:
    """
    Нормализовать номер стандарта для поиска в базе.
    
    Args:
        standard_type: Тип стандарта (ГОСТ, ОСТ, DIN, ISO)
        standard_number: Номер стандарта
        
    Returns:
        Нормализованный номер для поиска
    """
    if not standard_number:
        return ""
    
    # Нормализуем тип
    standard_type = standard_type.upper().strip()
    if standard_type == 'ОСТ':
        standard_type = 'OST'
    
    # Нормализуем номер
    normalized_number = normalize_standard_text(standard_number)
    
    # Убираем тип из номера если он там есть
    normalized_number = re.sub(r'^(ГОСТ|ОСТ|OST|DIN|ISO)\s*', '', normalized_number, flags=re.IGNORECASE)
    
    # Формируем стандартный ID для поиска
    # Формат: "OST_33080-80" или "GOST_7798-30"
    standard_id = f"{standard_type}_{normalized_number}"
    
    return standard_id


def get_search_variants(standard_type: str, standard_number: str) -> list:
    """
    Получить варианты поиска стандарта.
    
    Генерирует различные варианты написания для поиска:
    - С пробелами и без
    - С дефисами и без
    - С префиксом и без (для ОСТ)
    
    Args:
        standard_type: Тип стандарта
        standard_number: Номер стандарта
        
    Returns:
        Список вариантов для поиска
    """
    variants = []
    
    # Парсим обозначение
    parsed = parse_standard_designation(f"{standard_type} {standard_number}")
    if not parsed:
        # Если не распарсилось, используем как есть
        variants.append(normalize_standard_number(standard_type, standard_number))
        return variants
    
    std_type = parsed['type']
    full_number = parsed.get('full_number', standard_number)
    
    # Базовый вариант
    variants.append(f"{std_type}_{full_number}")
    
    # Вариант без дефиса (если есть)
    if '-' in full_number:
        variants.append(f"{std_type}_{full_number.replace('-', '')}")
    
    # Вариант с пробелом вместо дефиса
    if '-' in full_number:
        variants.append(f"{std_type}_{full_number.replace('-', ' ')}")
    
    # Для ОСТ с префиксом - варианты с префиксом и без
    if std_type == 'OST' and 'prefix' in parsed:
        prefix = parsed['prefix']
        number = parsed['number']
        year = parsed['year']
        # С префиксом
        variants.append(f"OST_{prefix}_{number}-{year}")
        variants.append(f"OST_{prefix}_{number}{year}")
        # Без префикса
        variants.append(f"OST_{number}-{year}")
        variants.append(f"OST_{number}{year}")
    
    return list(set(variants))  # Убираем дубликаты
