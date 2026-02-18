"""
Intent Detector - rule-based определение интентов пользователя.
Без использования LLM, только regex и ключевые слова.
"""

import re
import logging
from typing import Dict, Optional, List

from app.dialog.constants import Intent, INTENT_PRIORITY

logger = logging.getLogger(__name__)


class IntentDetector:
    """
    Rule-based детектор интентов.
    
    Определяет намерения пользователя через:
    - Regex паттерны
    - Ключевые слова
    - Структурированные паттерны (стандарты, размеры)
    """
    
    def __init__(self):
        """Инициализация детектора интентов."""
        # Паттерны для стандартов (ГОСТ, ОСТ, ISO, DIN и т.д.)
        # Улучшенные паттерны с обязательным дефисом для номеров стандартов
        self.standard_patterns = [
            r'\b(?:ГОСТ|GOST)\s*\d+[-–]\d+',  # ГОСТ 7798-70
            r'\b(?:ОСТ|OST)\s*\d+(?:\s+\d+)?[-–]\d+',  # ОСТ 1 33056-80
            r'\bISO\s*\d+[-–:]\d+',  # ISO 965-1
            r'\bDIN\s*\d+[-–]\d+',  # DIN 912-88
            r'\bANSI\s*\d+[-–]\d+',  # ANSI B18.2.1-1996
            r'\bASME\s*\d+[-–]\d+',  # ASME B18.2.1-1996
            r'\bJIS\s*\d+[-–]\d+',  # JIS B 1001-1998
            r'\bEN\s*\d+[-–]\d+',  # EN 1092-1
            r'\bBS\s*\d+[-–]\d+',  # BS 4500-1
        ]
        
        # Компилируем паттерны
        self.compiled_standard_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.standard_patterns
        ]
    
    def detect(self, message: str) -> Dict[str, any]:
        """
        Определить интент сообщения.
        
        Args:
            message: Текст сообщения пользователя
            
        Returns:
            Словарь с полями:
            - intent: Intent enum
            - confidence: float (0.0-1.0)
            - metadata: дополнительная информация
        """
        if not message or not message.strip():
            return {
                'intent': Intent.UNKNOWN,
                'confidence': 0.0,
                'metadata': {}
            }
        
        message_lower = message.lower().strip()
        
        # Собираем все возможные интенты с их приоритетами
        detected_intents = []
        
        # 1. RESET (высший приоритет)
        if self._is_reset(message_lower):
            detected_intents.append({
                'intent': Intent.RESET,
                'confidence': 1.0,
                'metadata': {}
            })
        
        # 2. STANDARD_REQUEST (высокий приоритет)
        standard_match = self._detect_standard(message)
        if standard_match:
            detected_intents.append({
                'intent': Intent.STANDARD_REQUEST,
                'confidence': 0.95,
                'metadata': {
                    'standard_code': standard_match['code'],
                    'family': standard_match['family'],
                    'full_match': standard_match['full_match']
                }
            })
        
        # 3. CALCULATION_REQUEST
        # Проверяем фразы типа "просто посчитать режимы" для выхода из STANDARD_MODE
        if self._is_calculation_request(message_lower):
            detected_intents.append({
                'intent': Intent.CALCULATION_REQUEST,
                'confidence': 0.8,
                'metadata': {
                    'has_material': self._has_material_keywords(message_lower),
                    'has_dimensions': self._has_dimension_keywords(message_lower),
                    'has_operation': self._has_operation_keywords(message_lower),
                    'is_simple_request': 'просто посчитать' in message_lower or 'посчитать режимы' in message_lower,
                }
            })
        
        # 4. UPLOAD_STANDARD
        if self._is_upload_request(message_lower):
            detected_intents.append({
                'intent': Intent.UPLOAD_STANDARD,
                'confidence': 0.85,
                'metadata': {}
            })
        
        # 5. GREETING
        if self._is_greeting(message_lower):
            detected_intents.append({
                'intent': Intent.GREETING,
                'confidence': 0.9,
                'metadata': {}
            })
        
        # 6. HELP
        if self._is_help(message_lower):
            detected_intents.append({
                'intent': Intent.HELP,
                'confidence': 0.9,
                'metadata': {}
            })
        
        # Если ничего не найдено
        if not detected_intents:
            return {
                'intent': Intent.UNKNOWN,
                'confidence': 0.0,
                'metadata': {}
            }
        
        # Выбираем интент с наивысшим приоритетом
        best_intent = min(
            detected_intents,
            key=lambda x: INTENT_PRIORITY.get(x['intent'], 99)
        )
        
        logger.debug(
            f"Intent detected: {best_intent['intent'].value} "
            f"(confidence={best_intent['confidence']:.2f}) for message: {message[:50]}"
        )
        
        return best_intent
    
    def _is_reset(self, message: str) -> bool:
        """Проверить является ли сообщение командой сброса."""
        reset_keywords = [
            'сброс', 'reset', 'начать заново', 'заново', 'отмена',
            'отменить', 'стоп', 'stop', 'очистить', 'clear',
            'сбросить', 'начать сначала'
        ]
        return any(keyword in message for keyword in reset_keywords)
    
    def _detect_standard(self, message: str) -> Optional[Dict[str, str]]:
        """
        Обнаружить упоминание стандарта в сообщении.
        
        Returns:
            Словарь с полями: code, family, full_match или None
        """
        for pattern in self.compiled_standard_patterns:
            match = pattern.search(message)
            if match:
                full_match = match.group(0)
                
                # Определяем семейство
                family = self._extract_family(full_match)
                
                # Извлекаем код
                code = self._extract_code(full_match)
                
                return {
                    'code': code,
                    'family': family,
                    'full_match': full_match
                }
        
        return None
    
    def _extract_family(self, standard_text: str) -> str:
        """Извлечь семейство стандарта."""
        text_upper = standard_text.upper()
        
        if text_upper.startswith('ГОСТ') or text_upper.startswith('GOST'):
            return 'GOST'
        elif text_upper.startswith('ОСТ') or text_upper.startswith('OST'):
            return 'OST'
        elif text_upper.startswith('ISO'):
            return 'ISO'
        elif text_upper.startswith('DIN'):
            return 'DIN'
        elif text_upper.startswith('ANSI'):
            return 'ANSI'
        elif text_upper.startswith('ASME'):
            return 'ASME'
        elif text_upper.startswith('JIS'):
            return 'JIS'
        elif text_upper.startswith('EN'):
            return 'EN'
        elif text_upper.startswith('BS'):
            return 'BS'
        
        return 'UNKNOWN'
    
    def _extract_code(self, standard_text: str) -> str:
        """Извлечь код стандарта."""
        # Убираем название семейства и оставляем только код
        code = re.sub(r'^(?:ГОСТ|GOST|ОСТ|OST|ISO|DIN|ANSI|ASME|JIS|EN|BS)\s*', '', 
                     standard_text, flags=re.IGNORECASE)
        return code.strip()
    
    def _is_calculation_request(self, message: str) -> bool:
        """Проверить является ли сообщение запросом расчета."""
        calculation_keywords = [
            'рассчитать', 'расчет', 'посчитать', 'вычислить',
            'калькулятор', 'нужен расчет', 'нужен калькулятор',
            'помоги рассчитать', 'помоги посчитать',
            'просто посчитать режимы', 'посчитать режимы'
        ]
        
        # Также проверяем наличие размеров или материалов
        has_keywords = any(keyword in message for keyword in calculation_keywords)
        has_data = (self._has_material_keywords(message) or 
                   self._has_dimension_keywords(message) or
                   self._has_operation_keywords(message))
        
        return has_keywords or has_data
    
    def _has_material_keywords(self, message: str) -> bool:
        """Проверить наличие ключевых слов материалов."""
        material_keywords = [
            'алюминий', 'сталь', 'титан', 'медь', 'латунь',
            'бронза', 'пластик', 'дерево', 'нержавейка',
            'aluminum', 'steel', 'titanium', 'copper', 'brass'
        ]
        return any(keyword in message for keyword in material_keywords)
    
    def _has_dimension_keywords(self, message: str) -> bool:
        """Проверить наличие размеров."""
        # Паттерны размеров: "50 до 200", "50-200", "50x200", "Ø50"
        dimension_patterns = [
            r'\d+\s*(?:до|to|-|×|x)\s*\d+',  # "50 до 200"
            r'[Øø]\s*\d+',  # "Ø50"
            r'\d+\s*мм',  # "50 мм"
            r'\d+\s*mm',  # "50 mm"
        ]
        
        for pattern in dimension_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        
        return False
    
    def _has_operation_keywords(self, message: str) -> bool:
        """Проверить наличие операций."""
        operation_keywords = [
            'токарка', 'фрезеровка', 'сверление', 'нарезка',
            'turning', 'milling', 'drilling', 'threading'
        ]
        return any(keyword in message for keyword in operation_keywords)
    
    def _is_upload_request(self, message: str) -> bool:
        """Проверить является ли сообщение запросом загрузки."""
        upload_keywords = [
            'загрузить', 'загрузи', 'upload', 'добавить стандарт',
            'добавь стандарт', 'импорт', 'import'
        ]
        return any(keyword in message for keyword in upload_keywords)
    
    def _is_greeting(self, message: str) -> bool:
        """Проверить является ли сообщение приветствием."""
        greeting_keywords = [
            'привет', 'здравствуй', 'здравствуйте', 'добрый день',
            'добрый вечер', 'доброе утро', 'hi', 'hello', 'hey',
            'доброго времени суток'
        ]
        return any(keyword in message for keyword in greeting_keywords)
    
    def _is_help(self, message: str) -> bool:
        """Проверить является ли сообщение запросом помощи."""
        help_keywords = [
            'помощь', 'help', 'помоги', 'как', 'что делать',
            'инструкция', 'руководство', 'справка'
        ]
        return any(keyword in message for keyword in help_keywords)
