"""
Intent Parser - определяет намерение пользователя.
Различает: приветствие, мета-вопросы, инженерные запросы, шум.
"""

import re
import logging
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Типы намерений пользователя."""
    GREETING = "greeting"  # Приветствие, small talk
    META_CAPABILITIES = "meta_capabilities"  # "что ты можешь", "чем полезен"
    HELP = "help"  # "помощь", "как работать"
    STANDARD_PART = "standard_part"  # ГОСТ / ОСТ / DIN / ISO - стандартная деталь
    ENGINEERING = "engineering"  # Инженерный запрос (режимы, расчеты)
    WORK_MANAGEMENT = "work_management"  # Работа с сохраненными работами
    HISTORY = "history"  # Запрос истории
    NOISE = "noise"  # Шум, неразборчиво


class IntentParser:
    """
    Парсер намерений пользователя.
    Определяет тип запроса до обработки через FSM.
    """
    
    def __init__(self):
        """Инициализация парсера интентов."""
        # Паттерны для приветствий
        self.greeting_patterns = [
            r'^(привет|здравствуй|здравствуйте|добрый\s+(день|вечер|утро)|hi|hello|hey|салют|здарова|ку|але|алё)$',
            r'^(привет|здравствуй|здравствуйте|hi|hello|hey|салют|здарова|ку|але|алё)\s*[!\.]*$',
        ]
        
        # Паттерны для мета-вопросов о возможностях
        self.meta_capabilities_patterns = [
            r'что\s+ты\s+можешь',
            r'чем\s+ты\s+полезен',
            r'что\s+ты\s+умеешь',
            r'расскажи\s+о\s+себе',
            r'кто\s+ты',
            r'что\s+за\s+бот',
            r'твои\s+возможности',
            r'what\s+can\s+you\s+do',
            r'what\s+are\s+you',
            r'who\s+are\s+you',
        ]
        
        # Паттерны для помощи
        self.help_patterns = [
            r'помощь|help',
            r'как\s+работать',
            r'как\s+пользоваться',
            r'инструкция',
            r'руководство',
            r'как\s+начать',
        ]
        
        # Паттерны для работы с работами
        self.work_management_patterns = [
            r'мои\s+работы',
            r'список\s+работ',
            r'работы',
            r'сохранить\s+работу',
            r'добавить\s+работу',
            r'работа\s+w\d+',
            r'удалить\s+w\d+',
            r'my\s+works',
            r'save\s+work',
        ]
        
        # Паттерны для истории
        self.history_patterns = [
            r'история|историю|покажи\s+историю',
            r'history|show\s+history',
        ]
        
        # Паттерны для стандартных деталей (ГОСТ/ОСТ/DIN/ISO)
        self.standard_patterns = [
            r'\bгост\s*\d+[-\s]*\d+',  # ГОСТ 7798-30, ГОСТ 7798 30
            r'\bост\s*\d+[-\s]*\d+',  # ОСТ 1 31102-80, ОСТ 1 31102 80
            r'\bdin\s*\d+',  # DIN 912, DIN 933
            r'\biso\s*\d+',  # ISO 4014, ISO 4762
            r'\bгост\s*\d+[-\s]*\d+',  # гост (кириллица)
            r'\bост\s*\d+[-\s]*\d+',  # ост (кириллица)
            r'стандарт\s*\d+',  # стандарт 7798
            r'по\s+госту',  # по госту
            r'по\s+ост',  # по ост
            r'деталь\s+по\s+госту',  # деталь по госту
            r'изготовить\s+по\s+госту',  # изготовить по госту
        ]
        
        # Паттерны для инженерных запросов
        self.engineering_keywords = [
            # Материалы
            r'сталь|алюминий|титан|нержавейка|чугун|латунь|медь',
            r'steel|aluminum|titanium|stainless',
            # Операции
            r'токарка|фрезер|сверл|расточ',
            r'turning|milling|drilling',
            # Параметры
            r'оборот|rpm|скорость|vc|подача|feed|глубина|ap',
            r'диаметр|diameter|ø|Ø',
            r'режим|режимы|расчёт|расчет|подбери|подобрать',
            r'чернов|чистов|получист',
            r'roughing|finishing',
            # Станки
            r'станок|машина|machine|cnc|чпу',
            # Инструменты
            r'инструмент|tool|пластина|insert',
            r'cnmg|wnmg|tnmg|dnmg',
        ]
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        Определить намерение пользователя.
        
        Args:
            text: Текст сообщения пользователя
            
        Returns:
            Словарь с интентом и метаданными
        """
        if not text or not text.strip():
            return {
                'intent': Intent.NOISE,
                'confidence': 0.0,
                'reason': 'Пустое сообщение'
            }
        
        text_lower = text.lower().strip()
        text_clean = re.sub(r'[^\w\s]', '', text_lower)
        
        # ============================================================================
        # ПРАВИЛО №1 (ЖЕЛЕЗНОЕ): СТАНДАРТЫ ПРОВЕРЯЮТСЯ ПЕРВЫМИ
        # ============================================================================
        # Если в тексте есть ГОСТ/ОСТ/DIN/ISO → это STANDARD_PART
        # НЕ проверяем наличие в базе, НЕ проверяем номер - СНАЧАЛА признаем стандарт
        
        # Паттерн для стандартов: "ОСТ 1 33056-80", "ГОСТ 7798-30", "DIN 912"
        # Для ОСТ может быть формат "1 33056-80" - нужно захватить весь номер
        standard_patterns = [
            r'\b(гост|ост|din|iso)\s+(\d+\s+\d+[-\s]\d+)',  # ОСТ 1 33056-80
            r'\b(гост|ост|din|iso)\s+(\d+[-\s]\d+)',  # ГОСТ 7798-30, ОСТ 33056-80
            r'\b(гост|ост|din|iso)\s+(\d+)',  # DIN 912, ISO 4014
        ]
        
        for pattern in standard_patterns:
            standard_match = re.search(pattern, text_lower, re.IGNORECASE)
            if standard_match:
                standard_type = standard_match.group(1).upper()
                standard_number = standard_match.group(2).strip()
                
                # Нормализуем номер: заменяем пробелы на дефисы где нужно
                # "1 33056-80" -> "1 33056-80" (оставляем как есть)
                # "33056-80" -> "33056-80"
                # "7798 30" -> "7798-30"
                standard_number = re.sub(r'\s+', ' ', standard_number)  # Нормализуем пробелы
                
                return {
                    'intent': Intent.STANDARD_PART,
                    'confidence': 0.95,
                    'reason': f'Стандарт распознан: {standard_type} {standard_number}',
                    'standard_type': standard_type,
                    'standard_number': standard_number
                }
        
        # Также проверяем упоминания стандартов без номера
        if re.search(r'\b(гост|ост|din|iso)\b', text_lower, re.IGNORECASE):
            # Есть упоминание стандарта, но номер не извлечен
            standard_type_match = re.search(r'\b(гост|ост|din|iso)\b', text_lower, re.IGNORECASE)
            standard_type = standard_type_match.group(1).upper() if standard_type_match else None
            
            return {
                'intent': Intent.STANDARD_PART,
                'confidence': 0.85,
                'reason': f'Упоминание стандарта ({standard_type})',
                'standard_type': standard_type,
                'standard_number': None
            }
        
        # ============================================================================
        # ОСТАЛЬНЫЕ ПРОВЕРКИ (после стандартов)
        # ============================================================================
        
        # 1. Проверяем приветствие (строгое совпадение)
        for pattern in self.greeting_patterns:
            if re.match(pattern, text_lower, re.IGNORECASE):
                return {
                    'intent': Intent.GREETING,
                    'confidence': 0.95,
                    'reason': 'Приветствие'
                }
        
        # 2. Проверяем мета-вопросы о возможностях
        for pattern in self.meta_capabilities_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return {
                    'intent': Intent.META_CAPABILITIES,
                    'confidence': 0.9,
                    'reason': 'Вопрос о возможностях бота'
                }
        
        # 3. Проверяем запросы помощи
        for pattern in self.help_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return {
                    'intent': Intent.HELP,
                    'confidence': 0.9,
                    'reason': 'Запрос помощи'
                }
        
        # 4. Проверяем работу с сохраненными работами
        for pattern in self.work_management_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return {
                    'intent': Intent.WORK_MANAGEMENT,
                    'confidence': 0.85,
                    'reason': 'Работа с сохраненными работами'
                }
        
        # 5. Проверяем запросы истории
        for pattern in self.history_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return {
                    'intent': Intent.HISTORY,
                    'confidence': 0.85,
                    'reason': 'Запрос истории'
                }
        
        # 6. Проверяем инженерные запросы (только если не стандарт - стандарты уже проверены выше)
        engineering_score = 0
        for keyword in self.engineering_keywords:
            if re.search(keyword, text_lower, re.IGNORECASE):
                engineering_score += 1
        
        # Если есть хотя бы 2 инженерных ключевых слова или явные команды
        if engineering_score >= 2:
            return {
                'intent': Intent.ENGINEERING,
                'confidence': min(0.9, 0.5 + engineering_score * 0.1),
                'reason': f'Инженерный запрос ({engineering_score} ключевых слов)'
            }
        
        # Явные команды на расчет
        if re.search(r'режим|расчёт|расчет|подбери|подобрать', text_lower, re.IGNORECASE):
            return {
                'intent': Intent.ENGINEERING,
                'confidence': 0.8,
                'reason': 'Явная команда на расчет'
            }
        
        # 7. Проверяем на шум (короткие бессмысленные сообщения)
        if len(text_clean) <= 3 and not any(c.isdigit() for c in text_clean):
            # Если это не число и короткое - вероятно шум
            if not re.match(r'^(да|нет|ок|ok|yes|no)$', text_lower):
                return {
                    'intent': Intent.NOISE,
                    'confidence': 0.7,
                    'reason': 'Короткое сообщение без смысла'
                }
        
        # 8. Если ничего не подошло, но есть хоть какое-то содержание
        if len(text_clean) > 3:
            # НЕ предполагаем инженерный запрос автоматически
            # Это может быть просто разговор или неопределенный запрос
            return {
                'intent': Intent.NOISE,
                'confidence': 0.3,
                'reason': 'Неопределенный запрос - требуется уточнение'
            }
        
        # 9. Иначе - шум
        return {
            'intent': Intent.NOISE,
            'confidence': 0.5,
            'reason': 'Не удалось определить намерение'
        }
    
    def is_engineering_intent(self, text: str) -> bool:
        """
        Быстрая проверка - является ли запрос инженерным.
        
        Args:
            text: Текст сообщения
            
        Returns:
            True если инженерный запрос
        """
        result = self.parse(text)
        return result['intent'] == Intent.ENGINEERING
    
    def should_activate_fsm(self, text: str) -> bool:
        """
        Определить, нужно ли активировать FSM.
        
        Args:
            text: Текст сообщения
            
        Returns:
            True если нужно активировать FSM
        """
        result = self.parse(text)
        return result['intent'] == Intent.ENGINEERING and result['confidence'] >= 0.5
