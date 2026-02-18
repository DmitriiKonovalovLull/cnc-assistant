"""
IntentDetector - детектор намерений пользователя с правильным приоритетом.
Порядок проверки ЖЁСТКИЙ:
1. Команды (/start, help)
2. Фото
3. Стандарты (только явные обозначения: M20, H7, Ra 1.6)
4. Технологический текст
5. Fallback
"""

import re
import logging
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Типы намерений пользователя."""
    COMMAND = "command"  # Команды (/start, /help)
    PHOTO = "photo"  # Фото
    GREETING = "greeting"  # Приветствие (привет, hi, hello)
    CANCEL = "cancel"  # Отмена (нет, отмена)
    STANDARD = "standard"  # Явные обозначения стандартов (M20, H7, Ra 1.6)
    PROCESS = "process"  # Технологический запрос (режимы, расчеты)
    CALCULATOR = "calculator"  # Калькулятор (калькулятор, расчёт)
    HELP = "help"  # Помощь
    UNKNOWN = "unknown"  # Неопределенный


class IntentDetector:
    """
    Детектор намерений с правильным приоритетом.
    Стандарты проверяются ТОЛЬКО для явных обозначений, не блокируют технологические запросы.
    """
    
    # Паттерны для ЯВНЫХ обозначений стандартов (не упоминаний ГОСТ/ОСТ в тексте)
    STANDARD_DESIGNATION_PATTERNS = [
        # Резьбы: M20, M42x1.5, M42x1.5-6g
        r'\bM\d+(?:x\d+(?:\.\d+)?)?(?:[-]\d+[ghGH])?\b',
        # Допуски: H7, g6, IT7, Ø50 H7
        r'[Øø]\s*\d+\s*[HhGg][0-9]',  # Ø50 H7
        r'\b[HhGg][0-9]\b',  # H7, g6
        r'\bIT[0-9]+\b',  # IT7, IT6
        # Шероховатость: Ra 1.6, Ra0.8, Rz 3.2
        r'\bR[az]\s*[\d.]+',
        # Посадки: H7/k6, H7g6
        r'\b[Hh][0-9]\s*[/-]\s*[a-z][0-9]\b',
    ]
    
    # Паттерны для технологических запросов
    PROCESS_KEYWORDS = [
        r'режим|режимы|расчёт|расчет|подбери|подобрать',
        r'диаметр|diameter|ø|Ø',
        r'чернов|чистов|получист',
        r'станок|машина|machine',
        r'материал|material',
        r'инструмент|tool',
        r'скорость|vc|rpm|оборот',
        r'подача|feed',
        r'глубина|ap',
        r'токар|фрезер|сверл|расточ',
        r'turning|milling|drilling',
    ]
    
    # Паттерны для помощи
    HELP_KEYWORDS = [
        r'что\s+ты\s+можешь',
        r'помощь|help',
        r'как\s+работать',
    ]
    
    # Паттерны для приветствия
    GREETING_KEYWORDS = [
        r'^(привет|здравствуй|здравствуйте|hi|hello|hey|салют|здарова|ку)$',
        r'^(привет|здравствуй|здравствуйте|hi|hello|hey|салют|здарова|ку)\s*[!\.]*$',
    ]
    
    # Паттерны для отмены
    CANCEL_KEYWORDS = [
        r'^(нет|отмена|cancel|отменить|не надо|не нужно)$',
    ]
    
    # Паттерны для калькулятора
    CALCULATOR_KEYWORDS = [
        r'калькулятор|calculator|расчёт|расчет|посчитать|вычислить',
    ]
    
    def detect_intent(self, text: Optional[str], has_photo: bool = False) -> IntentType:
        """
        Определить намерение пользователя.
        
        Порядок проверки:
        1. Фото
        2. Стандарты (только явные обозначения)
        3. Технологический запрос
        4. Помощь
        5. Неопределенный
        
        Args:
            text: Текст сообщения
            has_photo: Есть ли фото в сообщении
            
        Returns:
            IntentType
        """
        # 1. Фото обрабатывается отдельно в telegram_bot.py, но здесь для полноты
        if has_photo:
            return IntentType.PHOTO
        
        if not text or not text.strip():
            return IntentType.UNKNOWN
        
        text_lower = text.lower().strip()
        text_clean = text_lower.strip()
        
        # 1. Проверяем приветствие (ПЕРВЫМ!)
        for pattern in self.GREETING_KEYWORDS:
            if re.match(pattern, text_clean, re.IGNORECASE):
                logger.debug("Greeting detected")
                return IntentType.GREETING
        
        # 2. Проверяем отмену
        for pattern in self.CANCEL_KEYWORDS:
            if re.match(pattern, text_clean, re.IGNORECASE):
                logger.debug("Cancel detected")
                return IntentType.CANCEL
        
        # 3. Проверяем калькулятор
        for keyword in self.CALCULATOR_KEYWORDS:
            if re.search(keyword, text_lower, re.IGNORECASE):
                logger.debug("Calculator detected")
                return IntentType.CALCULATOR
        
        # 4. Проверяем ЯВНЫЕ обозначения стандартов (M20, H7, Ra 1.6)
        # Это НЕ упоминания ГОСТ/ОСТ в тексте, а именно обозначения
        for pattern in self.STANDARD_DESIGNATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(f"Standard designation detected: {pattern}")
                return IntentType.STANDARD
        
        # 5. Проверяем технологический запрос
        # Если есть ключевые слова технологического запроса
        process_score = 0
        for keyword in self.PROCESS_KEYWORDS:
            if re.search(keyword, text_lower, re.IGNORECASE):
                process_score += 1
        
        # Если есть хотя бы 2 ключевых слова или явные команды на расчет
        if process_score >= 2:
            return IntentType.PROCESS
        
        # Явные команды на расчет
        if re.search(r'режим|расчёт|расчет|подбери|подобрать', text_lower, re.IGNORECASE):
            return IntentType.PROCESS
        
        # 6. Проверяем помощь
        for keyword in self.HELP_KEYWORDS:
            if re.search(keyword, text_lower, re.IGNORECASE):
                return IntentType.HELP
        
        # 7. Если ничего не подошло - неопределенный
        return IntentType.UNKNOWN
    
    def is_standard_designation(self, text: str) -> bool:
        """
        Проверить, является ли текст ЯВНЫМ обозначением стандарта.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если это явное обозначение стандарта
        """
        if not text or len(text.strip()) > 80:
            return False
        
        # Проверяем только короткие обозначения (M20, H7, Ra 1.6)
        for pattern in self.STANDARD_DESIGNATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def is_process_request(self, text: str) -> bool:
        """
        Проверить, является ли текст технологическим запросом.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если это технологический запрос
        """
        return self.detect_intent(text) == IntentType.PROCESS
