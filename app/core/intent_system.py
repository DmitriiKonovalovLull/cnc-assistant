"""
Универсальная система определения намерений пользователя.
Intent-based архитектура вместо FSM.
"""

import re
import logging
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Универсальные намерения пользователя."""
    GREETING = "greeting"
    HELP = "help"
    STANDARD_LOOKUP = "standard_lookup"
    PROCESS_CALCULATION = "process_calculation"
    FIT_CALCULATION = "fit_calculation"
    THREAD_CALCULATION = "thread_calculation"
    SURFACE_CALCULATION = "surface_calculation"
    POWER_CHECK = "power_check"
    DOWNLOAD_STANDARDS = "download_standards"
    ADMIN_CHECK = "admin_check"
    STANDARD_INTEGRITY_CHECK = "standard_integrity_check"
    UNKNOWN = "unknown"


class IntentDetector:
    """
    Детектор намерений пользователя.
    Определяет что хочет пользователь на основе текста сообщения.
    """
    
    def detect_intent(self, text: Optional[str]) -> Intent:
        """
        Определить намерение пользователя.
        
        Args:
            text: Текст сообщения
            
        Returns:
            Intent - тип намерения
        """
        if not text or not text.strip():
            return Intent.UNKNOWN
        
        t = text.lower().strip()
        
        # 1. Приветствие
        if t in ["привет", "hello", "hi", "здравствуй", "здравствуйте", "hey"]:
            return Intent.GREETING
        
        # 2. Помощь
        if any(x in t for x in ["что ты можешь", "помощь", "help", "как работать", "инструкция"]):
            return Intent.HELP
        
        # 3. Проверка базы стандартов
        if any(x in t for x in ["проверка базы", "проверь базу", "база нормалей", "стандарты загружены", "check standards"]):
            return Intent.STANDARD_INTEGRITY_CHECK
        
        # 4. Загрузка стандартов
        if any(x in t for x in ["скачай стандарты", "загрузи стандарты", "обнови стандарты", "download standards", "update standards"]):
            return Intent.DOWNLOAD_STANDARDS
        
        # 5. Поиск стандарта
        if any(x in t for x in ["гост", "ост", "iso", "din", "ansi", "asme", "jis", "en", "стандарт"]):
            return Intent.STANDARD_LOOKUP
        
        # 6. Расчет режимов обработки
        if any(x in t for x in ["режим", "режимы", "диаметр", "чернов", "чист", "скорость", "подача", "vc", "rpm"]):
            return Intent.PROCESS_CALCULATION
        
        # 7. Расчет посадок
        if any(x in t for x in ["h7", "g6", "f7", "посадк", "fit", "допуск", "tolerance"]):
            return Intent.FIT_CALCULATION
        
        # 8. Расчет резьбы
        if any(x in t for x in ["m20", "m42", "резьб", "thread", "шаг резьбы", "pitch"]):
            return Intent.THREAD_CALCULATION
        
        # 9. Расчет шероховатости
        if any(x in t for x in ["ra", "rz", "шероховатость", "roughness", "чистота"]):
            return Intent.SURFACE_CALCULATION
        
        # 10. Проверка мощности
        if any(x in t for x in ["мощность", "power", "квт", "kw", "проверь мощность"]):
            return Intent.POWER_CHECK
        
        # 11. Админские команды (если нужно)
        if any(x in t for x in ["admin", "статистика", "stats", "логи"]):
            return Intent.ADMIN_CHECK
        
        return Intent.UNKNOWN
    
    def get_intent_metadata(self, text: Optional[str]) -> Dict[str, Any]:
        """
        Получить метаданные интента (для более сложной логики).
        
        Args:
            text: Текст сообщения
            
        Returns:
            Словарь с intent и дополнительными данными
        """
        intent = self.detect_intent(text)
        
        result = {
            'intent': intent,
            'confidence': 1.0,
            'text': text
        }
        
        # Дополнительная информация для некоторых интентов
        if intent == Intent.STANDARD_LOOKUP and text:
            # Извлекаем тип и номер стандарта
            parsed = self._parse_standard_from_text(text)
            if parsed:
                result['standard_type'] = parsed.get('type')
                result['standard_number'] = parsed.get('number')
        
        return result
    
    def _parse_standard_from_text(self, text: str) -> Optional[Dict[str, str]]:
        """Извлечь тип и номер стандарта из текста."""
        patterns = [
            r'\b(гост|ост|iso|din|ansi|asme|jis|en)\s+(\d+(?:\s+\d+)?[-\s]?\d*)',
            r'\b(гост|ост|iso|din|ansi|asme|jis|en)\s+(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    'type': match.group(1).upper(),
                    'number': match.group(2).strip()
                }
        
        return None
