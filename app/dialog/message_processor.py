"""
Message Processor - главный pipeline обработки сообщений.
Объединяет все компоненты: State Machine, Intent Detector, Context Manager, Validators.
"""

import logging
from typing import Dict, Any, Optional

from app.dialog.constants import DialogState, Intent
from app.dialog.state_machine import StateMachine
from app.dialog.intent_detector import IntentDetector
from app.dialog.context_manager import ContextManager
from app.dialog.validators import Validator

logger = logging.getLogger(__name__)


class MessageProcessor:
    """
    Главный процессор сообщений.
    
    Pipeline:
    1. Preprocessing
    2. Intent detection
    3. State validation
    4. State transition
    5. Handler execution
    6. Response
    """
    
    def __init__(self):
        """Инициализация процессора."""
        self.state_machine = StateMachine()
        self.intent_detector = IntentDetector()
        self.context_manager = ContextManager()
        self.validator = Validator()
    
    def process(self, user_id: int, message: str, **kwargs) -> Dict[str, Any]:
        """
        Обработать входящее сообщение.
        
        Args:
            user_id: ID пользователя
            message: Текст сообщения
            **kwargs: Дополнительные параметры (например, photo, file)
            
        Returns:
            Словарь с полями:
            - response: str - ответ пользователю
            - state: DialogState - новое состояние
            - intent: Intent - определенный интент
            - metadata: dict - дополнительная информация
        """
        # Логируем входящее сообщение
        logger.info(f"Processing message: user_id={user_id}, message={message[:100]}")
        
        # 1. Preprocessing
        message_clean = self._preprocess(message)
        
        # 2. Intent detection
        intent_result = self.intent_detector.detect(message_clean)
        intent = intent_result['intent']
        intent_metadata = intent_result.get('metadata', {})
        
        # Получаем текущее состояние
        current_state = self.state_machine.get(user_id)
        context = self.context_manager.get(user_id)
        
        logger.info(
            f"Intent detected: {intent.value}, "
            f"current_state: {current_state.value}, "
            f"user_id={user_id}"
        )
        
        # 3. Обработка по приоритету интентов
        
        # RESET - высший приоритет
        if intent == Intent.RESET:
            return self._handle_reset(user_id, message_clean)
        
        # STANDARD_REQUEST - высокий приоритет, игнорирует текущий state
        if intent == Intent.STANDARD_REQUEST:
            return self._handle_standard_request(
                user_id, message_clean, intent_metadata, current_state
            )
        
        # Остальные интенты обрабатываются с учетом текущего состояния
        if intent == Intent.CALCULATION_REQUEST:
            return self._handle_calculation_request(
                user_id, message_clean, current_state, context
            )
        
        if intent == Intent.GREETING:
            return self._handle_greeting(user_id, message_clean, current_state)
        
        if intent == Intent.HELP:
            return self._handle_help(user_id, message_clean)
        
        if intent == Intent.UPLOAD_STANDARD:
            return self._handle_upload(user_id, message_clean, current_state)
        
        # UNKNOWN - пытаемся обработать по текущему состоянию
        return self._handle_by_state(user_id, message_clean, current_state, context)
    
    def _preprocess(self, message: str) -> str:
        """
        Предобработка сообщения.
        
        Args:
            message: Исходное сообщение
            
        Returns:
            Очищенное сообщение
        """
        if not message:
            return ""
        
        # Убираем лишние пробелы
        cleaned = " ".join(message.split())
        
        return cleaned.strip()
    
    def _handle_reset(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Обработать команду сброса.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            
        Returns:
            Результат обработки
        """
        # Сбрасываем состояние
        self.state_machine.reset(user_id, reason="reset_command")
        
        # Очищаем контекст
        self.context_manager.clear(user_id)
        
        logger.info(f"Reset completed for user_id={user_id}")
        
        return {
            'response': "✅ Состояние сброшено. Начнем заново!",
            'state': DialogState.IDLE,
            'intent': Intent.RESET,
            'metadata': {}
        }
    
    def _handle_standard_request(
        self, user_id: int, message: str, 
        intent_metadata: Dict[str, Any], current_state: DialogState
    ) -> Dict[str, Any]:
        """
        Обработать запрос стандарта.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            intent_metadata: Метаданные интента
            current_state: Текущее состояние
            
        Returns:
            Результат обработки
        """
        # Стандарт имеет высокий приоритет - сбрасываем расчетный контекст
        self.context_manager.clear_calculation(user_id)
        
        # Переходим в состояние поиска стандарта
        self.state_machine.transition(
            user_id, DialogState.STANDARD_LOOKUP, 
            reason="standard_request_detected"
        )
        
        # Сохраняем данные стандарта в контекст
        standard_code = intent_metadata.get('code', '')
        standard_family = intent_metadata.get('family', '')
        
        self.context_manager.update(
            user_id,
            standard_code=standard_code,
            standard_family=standard_family
        )
        
        # TODO: Здесь должна быть интеграция с системой стандартов
        # Пока возвращаем заглушку
        response = (
            f"🔍 Ищу стандарт: {intent_metadata.get('full_match', standard_code)}\n"
            f"Семейство: {standard_family}\n"
            f"Код: {standard_code}"
        )
        
        return {
            'response': response,
            'state': DialogState.STANDARD_LOOKUP,
            'intent': Intent.STANDARD_REQUEST,
            'metadata': {
                'standard_code': standard_code,
                'standard_family': standard_family
            }
        }
    
    def _handle_calculation_request(
        self, user_id: int, message: str,
        current_state: DialogState, context: 'DialogContext'
    ) -> Dict[str, Any]:
        """
        Обработать запрос расчета.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            current_state: Текущее состояние
            context: Контекст пользователя
            
        Returns:
            Результат обработки
        """
        # Извлекаем данные из сообщения
        extracted_data = self.validator.extract_data_from_message(message)
        
        # Обновляем контекст
        if extracted_data:
            self.context_manager.update(user_id, **extracted_data)
            context = self.context_manager.get(user_id)
        
        # Определяем следующее состояние на основе контекста
        if not context.operation:
            # Нужна операция
            self.state_machine.transition(
                user_id, DialogState.WAITING_OPERATION,
                reason="operation_required"
            )
            return {
                'response': "Какую операцию нужно выполнить? (токарка, фрезеровка, сверление, нарезка)",
                'state': DialogState.WAITING_OPERATION,
                'intent': Intent.CALCULATION_REQUEST,
                'metadata': {}
            }
        
        if not context.material:
            # Нужен материал
            self.state_machine.transition(
                user_id, DialogState.WAITING_MATERIAL,
                reason="material_required"
            )
            return {
                'response': "Какой материал? (алюминий, сталь, титан, медь...)",
                'state': DialogState.WAITING_MATERIAL,
                'intent': Intent.CALCULATION_REQUEST,
                'metadata': {}
            }
        
        if not context.diameter_from and not context.diameter_to:
            # Нужны размеры
            self.state_machine.transition(
                user_id, DialogState.WAITING_DIMENSIONS,
                reason="dimensions_required"
            )
            return {
                'response': "Укажите размеры (например: 50 до 200 или Ø50)",
                'state': DialogState.WAITING_DIMENSIONS,
                'intent': Intent.CALCULATION_REQUEST,
                'metadata': {}
            }
        
        # Все данные есть - готов к расчету
        if context.is_calculation_ready():
            self.state_machine.transition(
                user_id, DialogState.CALCULATION_READY,
                reason="all_data_collected"
            )
            
            # TODO: Здесь должна быть интеграция с расчетным движком
            response = (
                f"✅ Данные собраны:\n"
                f"Операция: {context.operation}\n"
                f"Материал: {context.material}\n"
                f"Размеры: {context.diameter_from or 'N/A'} - {context.diameter_to or 'N/A'}\n\n"
                f"Расчет будет выполнен..."
            )
            
            return {
                'response': response,
                'state': DialogState.CALCULATION_READY,
                'intent': Intent.CALCULATION_REQUEST,
                'metadata': {
                    'context': context.to_dict()
                }
            }
        
        # Недостаточно данных
        return {
            'response': "Нужно больше информации для расчета. Укажите операцию, материал и размеры.",
            'state': current_state,
            'intent': Intent.CALCULATION_REQUEST,
            'metadata': {}
        }
    
    def _handle_greeting(
        self, user_id: int, message: str, current_state: DialogState
    ) -> Dict[str, Any]:
        """
        Обработать приветствие.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            current_state: Текущее состояние
            
        Returns:
            Результат обработки
        """
        # Приветствие НЕ меняет состояние
        # Только если мы в ERROR_STATE - можно сбросить
        
        if current_state == DialogState.ERROR_STATE:
            self.state_machine.transition(
                user_id, DialogState.IDLE,
                reason="greeting_after_error"
            )
            return {
                'response': "Привет! Чем могу помочь?",
                'state': DialogState.IDLE,
                'intent': Intent.GREETING,
                'metadata': {}
            }
        
        return {
            'response': "Привет! Чем могу помочь?",
            'state': current_state,  # Состояние не меняется
            'intent': Intent.GREETING,
            'metadata': {}
        }
    
    def _handle_help(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Обработать запрос помощи.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            
        Returns:
            Результат обработки
        """
        help_text = (
            "📖 Помощь:\n\n"
            "• Для расчета: укажите операцию, материал и размеры\n"
            "• Для поиска стандарта: напишите код (например: ОСТ 33056-80)\n"
            "• Для сброса: напишите 'сброс' или 'reset'\n"
            "• Примеры:\n"
            "  - 'токарка алюминий 50 до 200'\n"
            "  - 'ОСТ 33056-80'\n"
            "  - 'сброс'"
        )
        
        return {
            'response': help_text,
            'state': self.state_machine.get(user_id),  # Состояние не меняется
            'intent': Intent.HELP,
            'metadata': {}
        }
    
    def _handle_upload(
        self, user_id: int, message: str, current_state: DialogState
    ) -> Dict[str, Any]:
        """
        Обработать запрос загрузки стандарта.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            current_state: Текущее состояние
            
        Returns:
            Результат обработки
        """
        self.state_machine.transition(
            user_id, DialogState.UPLOAD_MODE,
            reason="upload_request"
        )
        
        return {
            'response': "📤 Режим загрузки стандарта. Отправьте PDF файл.",
            'state': DialogState.UPLOAD_MODE,
            'intent': Intent.UPLOAD_STANDARD,
            'metadata': {}
        }
    
    def _handle_by_state(
        self, user_id: int, message: str,
        current_state: DialogState, context: 'DialogContext'
    ) -> Dict[str, Any]:
        """
        Обработать сообщение на основе текущего состояния.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            current_state: Текущее состояние
            context: Контекст пользователя
            
        Returns:
            Результат обработки
        """
        # Извлекаем данные из сообщения
        extracted_data = self.validator.extract_data_from_message(message)
        
        if extracted_data:
            self.context_manager.update(user_id, **extracted_data)
            context = self.context_manager.get(user_id)
        
        # Обработка по состояниям
        if current_state == DialogState.WAITING_OPERATION:
            operation = self.validator.validate_operation(message)
            if operation:
                self.context_manager.update(user_id, operation=operation)
                self.state_machine.transition(
                    user_id, DialogState.WAITING_MATERIAL,
                    reason="operation_provided"
                )
                return {
                    'response': f"Операция: {operation}. Какой материал?",
                    'state': DialogState.WAITING_MATERIAL,
                    'intent': Intent.UNKNOWN,
                    'metadata': {}
                }
            else:
                return {
                    'response': "Не понял операцию. Укажите: токарка, фрезеровка, сверление или нарезка.",
                    'state': current_state,
                    'intent': Intent.UNKNOWN,
                    'metadata': {}
                }
        
        elif current_state == DialogState.WAITING_MATERIAL:
            material = self.validator.validate_material(message)
            if material:
                self.context_manager.update(user_id, material=material)
                self.state_machine.transition(
                    user_id, DialogState.WAITING_DIMENSIONS,
                    reason="material_provided"
                )
                return {
                    'response': f"Материал: {material}. Укажите размеры (например: 50 до 200).",
                    'state': DialogState.WAITING_DIMENSIONS,
                    'intent': Intent.UNKNOWN,
                    'metadata': {}
                }
            else:
                return {
                    'response': "Не понял материал. Укажите: алюминий, сталь, титан, медь...",
                    'state': current_state,
                    'intent': Intent.UNKNOWN,
                    'metadata': {}
                }
        
        elif current_state == DialogState.WAITING_DIMENSIONS:
            dimension_range = self.validator.validate_dimension_range(message)
            if dimension_range:
                self.context_manager.update(
                    user_id,
                    diameter_from=dimension_range[0],
                    diameter_to=dimension_range[1]
                )
                context = self.context_manager.get(user_id)
                
                if context.is_calculation_ready():
                    self.state_machine.transition(
                        user_id, DialogState.CALCULATION_READY,
                        reason="dimensions_provided"
                    )
                    return {
                        'response': "✅ Все данные собраны. Выполняю расчет...",
                        'state': DialogState.CALCULATION_READY,
                        'intent': Intent.UNKNOWN,
                        'metadata': {'context': context.to_dict()}
                    }
            else:
                return {
                    'response': "Не понял размеры. Укажите диапазон (например: 50 до 200) или диаметр (Ø50).",
                    'state': current_state,
                    'intent': Intent.UNKNOWN,
                    'metadata': {}
                }
        
        # Для остальных состояний возвращаем стандартный ответ
        return {
            'response': "Не понял. Напишите 'помощь' для справки или 'сброс' для начала заново.",
            'state': current_state,
            'intent': Intent.UNKNOWN,
            'metadata': {}
        }
