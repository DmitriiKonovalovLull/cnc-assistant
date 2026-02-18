"""
Message Processor - главный pipeline обработки сообщений.
Объединяет все компоненты: State Machine, Intent Detector, Context Manager, Validators.
"""

import logging
from typing import Dict, Any, Optional

from app.dialog.constants import DialogState, Intent, DialogMode
from app.dialog.state_machine import StateMachine
from app.dialog.intent_detector import IntentDetector
from app.dialog.context_manager import ContextManager
from app.dialog.validators import Validator
from app.dialog.mode_manager import ModeManager
from app.dialog.expression_calculator import ExpressionCalculator

logger = logging.getLogger(__name__)


class MessageProcessor:
    """
    Главный процессор сообщений.
    
    Pipeline:
    1. Check /start (полный reset)
    2. Detect calculator expression
    3. Detect intent
    4. Detect standard
    5. Route by mode
    6. Route by state
    7. Handler execution
    8. Response
    """
    
    def __init__(self):
        """Инициализация процессора."""
        self.state_machine = StateMachine()
        self.intent_detector = IntentDetector()
        self.context_manager = ContextManager()
        self.validator = Validator()
        self.mode_manager = ModeManager()
        self.expression_calculator = ExpressionCalculator()
    
    def process(self, user_id: int, message: str, **kwargs) -> Dict[str, Any]:
        """
        Обработать входящее сообщение.
        
        Args:
            user_id: ID пользователя
            message: Текст сообщения
            **kwargs: Дополнительные параметры (например, photo, file, is_start_command)
            
        Returns:
            Словарь с полями:
            - response: str - ответ пользователю
            - state: DialogState - новое состояние
            - mode: DialogMode - текущий режим
            - intent: Intent - определенный интент
            - metadata: dict - дополнительная информация
        """
        # Логируем входящее сообщение
        logger.info(f"Processing message: user_id={user_id}, message={message[:100]}")
        
        # 1. Check /start - полный reset
        if kwargs.get('is_start_command', False) or message.strip().lower() == '/start':
            return self._handle_start_command(user_id)
        
        # 2. Preprocessing
        message_clean = self._preprocess(message)
        
        # Получаем текущий режим и состояние
        current_mode = self.mode_manager.get(user_id)
        current_state = self.state_machine.get(user_id)
        context = self.context_manager.get(user_id)
        
        # 3. Detect calculator expression (высокий приоритет)
        if self.expression_calculator.is_expression(message_clean):
            return self._handle_calculator_expression(user_id, message_clean, current_mode)
        
        # 4. Intent detection
        intent_result = self.intent_detector.detect(message_clean)
        intent = intent_result['intent']
        intent_metadata = intent_result.get('metadata', {})
        
        # Проверяем есть ли стандарт в сообщении
        has_standard = intent == Intent.STANDARD_REQUEST
        
        logger.info(
            f"Intent detected: {intent.value}, "
            f"current_mode: {current_mode.value}, "
            f"current_state: {current_state.value}, "
            f"has_standard={has_standard}, "
            f"user_id={user_id}"
        )
        
        # 5. Route by mode and intent priority
        
        # RESET - высший приоритет
        if intent == Intent.RESET:
            return self._handle_reset(user_id, message_clean)
        
        # Проверка на выход из STANDARD_MODE
        if current_mode == DialogMode.STANDARD_MODE and intent == Intent.CALCULATION_REQUEST:
            # Пользователь хочет выйти из режима стандартов
            if "просто посчитать" in message_clean.lower() or "посчитать режимы" in message_clean.lower():
                self.mode_manager.set(user_id, DialogMode.CNC_CALC_MODE, reason="exit_standard_mode")
                self.context_manager.clear_calculation(user_id)
                return self._handle_calculation_request(
                    user_id, message_clean, current_state, context, has_standard=False
                )
        
        # STANDARD_REQUEST - высокий приоритет
        if intent == Intent.STANDARD_REQUEST:
            return self._handle_standard_request(
                user_id, message_clean, intent_metadata, current_state
            )
        
        # Обработка по режиму
        if current_mode == DialogMode.STANDARD_MODE:
            # В режиме стандартов - только работа со стандартами
            return self._handle_standard_mode(user_id, message_clean, intent, current_state)
        
        if current_mode == DialogMode.SIMPLE_CALCULATOR_MODE:
            # В режиме калькулятора - только вычисления
            if self.expression_calculator.is_expression(message_clean):
                return self._handle_calculator_expression(user_id, message_clean, current_mode)
            else:
                # Выход из калькулятора
                self.mode_manager.set(user_id, DialogMode.IDLE, reason="exit_calculator")
        
        # Остальные интенты обрабатываются с учетом текущего состояния
        if intent == Intent.CALCULATION_REQUEST:
            return self._handle_calculation_request(
                user_id, message_clean, current_state, context, has_standard=has_standard
            )
        
        if intent == Intent.GREETING:
            return self._handle_greeting(user_id, message_clean, current_state, current_mode)
        
        if intent == Intent.HELP:
            return self._handle_help(user_id, message_clean)
        
        if intent == Intent.UPLOAD_STANDARD:
            return self._handle_upload(user_id, message_clean, current_state)
        
        # UNKNOWN - пытаемся обработать по текущему состоянию
        return self._handle_by_state(
            user_id, message_clean, current_state, context, 
            has_standard=has_standard, current_mode=current_mode
        )
    
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
    
    def _handle_start_command(self, user_id: int) -> Dict[str, Any]:
        """
        Обработать команду /start - полный reset.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Результат обработки
        """
        # Полный reset: состояние, режим, контекст
        self.state_machine.reset(user_id, reason="start_command")
        self.mode_manager.reset(user_id, reason="start_command")
        self.context_manager.clear_all(user_id)
        
        logger.info(f"Full reset completed for user_id={user_id}")
        
        return {
            'response': "👋 Привет! Я CNC Assistant.\n\nЧто хотите сделать?",
            'state': DialogState.IDLE,
            'mode': DialogMode.IDLE,
            'intent': Intent.GREETING,
            'metadata': {'reset': True}
        }
    
    def _handle_calculator_expression(
        self, user_id: int, message: str, current_mode: DialogMode
    ) -> Dict[str, Any]:
        """
        Обработать математическое выражение.
        
        Args:
            user_id: ID пользователя
            message: Математическое выражение
            current_mode: Текущий режим
            
        Returns:
            Результат вычисления
        """
        # Переключаемся в режим калькулятора
        self.mode_manager.set(user_id, DialogMode.SIMPLE_CALCULATOR_MODE, reason="calculator_expression")
        
        # Вычисляем выражение
        result = self.expression_calculator.calculate(message)
        
        if result is not None:
            # Форматируем результат
            if isinstance(result, float) and result.is_integer():
                result_str = str(int(result))
            else:
                result_str = str(round(result, 10)).rstrip('0').rstrip('.')
            
            return {
                'response': f"🧮 {result_str}",
                'state': self.state_machine.get(user_id),  # Не меняем состояние
                'mode': DialogMode.SIMPLE_CALCULATOR_MODE,
                'intent': Intent.UNKNOWN,
                'metadata': {'expression': message, 'result': result}
            }
        else:
            return {
                'response': "❌ Не удалось вычислить выражение. Проверьте синтаксис.",
                'state': self.state_machine.get(user_id),
                'mode': DialogMode.SIMPLE_CALCULATOR_MODE,
                'intent': Intent.UNKNOWN,
                'metadata': {}
            }
    
    def _handle_standard_mode(
        self, user_id: int, message: str, intent: Intent, current_state: DialogState
    ) -> Dict[str, Any]:
        """
        Обработать сообщение в режиме стандартов.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            intent: Определенный интент
            current_state: Текущее состояние
            
        Returns:
            Результат обработки
        """
        # В режиме стандартов запрещено извлечение размеров
        # Только работа со стандартами
        
        if intent == Intent.CALCULATION_REQUEST:
            # Пользователь хочет выйти из режима стандартов
            self.mode_manager.set(user_id, DialogMode.CNC_CALC_MODE, reason="exit_standard_mode")
            self.context_manager.clear_calculation(user_id)
            context = self.context_manager.get(user_id)
            return self._handle_calculation_request(
                user_id, message, current_state, context, has_standard=False
            )
        
        # Остальные сообщения обрабатываются как стандарты
        return {
            'response': "🔍 Режим работы со стандартами. Укажите стандарт (например: ОСТ 33079-80) или напишите 'просто посчитать режимы' для выхода.",
            'state': current_state,
            'mode': DialogMode.STANDARD_MODE,
            'intent': intent,
            'metadata': {}
        }
    
    def _handle_reset(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Обработать команду сброса.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            
        Returns:
            Результат обработки
        """
        # Полный reset: состояние, режим, контекст
        self.state_machine.reset(user_id, reason="reset_command")
        self.mode_manager.reset(user_id, reason="reset_command")
        self.context_manager.clear_all(user_id)
        
        logger.info(f"Full reset completed for user_id={user_id}")
        
        return {
            'response': "✅ Состояние сброшено. Начнем заново!",
            'state': DialogState.IDLE,
            'mode': DialogMode.IDLE,
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
        # Переключаемся в режим стандартов
        self.mode_manager.set(user_id, DialogMode.STANDARD_MODE, reason="standard_request_detected")
        
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
            f"Код: {standard_code}\n\n"
            f"💡 Напишите 'просто посчитать режимы' для выхода из режима стандартов."
        )
        
        return {
            'response': response,
            'state': DialogState.STANDARD_LOOKUP,
            'mode': DialogMode.STANDARD_MODE,
            'intent': Intent.STANDARD_REQUEST,
            'metadata': {
                'standard_code': standard_code,
                'standard_family': standard_family,
                'no_work_number_required': True  # Не требовать номер работы
            }
        }
    
    def _handle_calculation_request(
        self, user_id: int, message: str,
        current_state: DialogState, context: 'DialogContext',
        has_standard: bool = False
    ) -> Dict[str, Any]:
        """
        Обработать запрос расчета.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            current_state: Текущее состояние
            context: Контекст пользователя
            has_standard: Есть ли стандарт в сообщении (запрещает извлечение размеров)
            
        Returns:
            Результат обработки
        """
        # Переключаемся в режим расчета режимов
        self.mode_manager.set(user_id, DialogMode.CNC_CALC_MODE, reason="calculation_request")
        
        # Определяем разрешено ли извлечение размеров
        # Размеры можно извлекать ТОЛЬКО в режиме CNC_CALC_MODE и состоянии WAITING_DIMENSIONS
        current_mode = self.mode_manager.get(user_id)
        allow_dimensions = (
            current_mode == DialogMode.CNC_CALC_MODE and 
            current_state == DialogState.WAITING_DIMENSIONS
        )
        
        # Извлекаем данные из сообщения с учетом контекста
        extracted_data = self.validator.extract_data_from_message(
            message, 
            allow_dimensions=allow_dimensions,
            has_standard=has_standard
        )
        
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
        
        # Проверяем required fields перед расчетом
        # НЕ создаем деталь автоматически - требуем все поля
        missing_fields = []
        if not context.operation:
            missing_fields.append("операция")
        if not context.material:
            missing_fields.append("материал")
        if not context.diameter_from and not context.diameter_to:
            missing_fields.append("размеры")
        
        # Если все required fields есть - готов к расчету
        if not missing_fields and context.is_calculation_ready():
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
                'mode': DialogMode.CNC_CALC_MODE,
                'intent': Intent.CALCULATION_REQUEST,
                'metadata': {
                    'context': context.to_dict(),
                    'no_work_number_required': True  # Не требовать номер работы для простого расчета
                }
            }
        
        # Недостаточно данных - запрашиваем недостающие поля
        if missing_fields:
            fields_text = ", ".join(missing_fields)
            return {
                'response': f"Для расчёта нужно указать: {fields_text}.",
                'state': current_state,
                'intent': Intent.CALCULATION_REQUEST,
                'metadata': {'missing_fields': missing_fields}
            }
        
        # Недостаточно данных (общий случай)
        return {
            'response': "Для расчёта режимов укажите:\n- материал\n- диаметр\n- тип обработки",
            'state': current_state,
            'mode': DialogMode.CNC_CALC_MODE,
            'intent': Intent.CALCULATION_REQUEST,
            'metadata': {
                'no_work_number_required': True  # Не требовать номер работы
            }
        }
    
    def _handle_greeting(
        self, user_id: int, message: str, current_state: DialogState, current_mode: DialogMode
    ) -> Dict[str, Any]:
        """
        Обработать приветствие.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            current_state: Текущее состояние
            current_mode: Текущий режим
            
        Returns:
            Результат обработки
        """
        # Приветствие НЕ меняет состояние и режим
        # Только если мы в ERROR_STATE - можно сбросить
        
        if current_state == DialogState.ERROR_STATE:
            self.state_machine.transition(
                user_id, DialogState.IDLE,
                reason="greeting_after_error"
            )
            return {
                'response': "Привет! Чем могу помочь?",
                'state': DialogState.IDLE,
                'mode': current_mode,
                'intent': Intent.GREETING,
                'metadata': {}
            }
        
        return {
            'response': "Привет! Чем могу помочь?",
            'state': current_state,  # Состояние не меняется
            'mode': current_mode,  # Режим не меняется
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
            'mode': self.mode_manager.get(user_id),  # Режим не меняется
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
            'mode': DialogMode.STANDARD_MODE,
            'intent': Intent.UPLOAD_STANDARD,
            'metadata': {}
        }
    
    def _handle_by_state(
        self, user_id: int, message: str,
        current_state: DialogState, context: 'DialogContext',
        has_standard: bool = False, current_mode: DialogMode = None
    ) -> Dict[str, Any]:
        """
        Обработать сообщение на основе текущего состояния.
        
        Args:
            user_id: ID пользователя
            message: Сообщение
            current_state: Текущее состояние
            context: Контекст пользователя
            has_standard: Есть ли стандарт в сообщении
            current_mode: Текущий режим
            
        Returns:
            Результат обработки
        """
        if current_mode is None:
            current_mode = self.mode_manager.get(user_id)
        
        # Размеры можно извлекать ТОЛЬКО в режиме CNC_CALC_MODE и состоянии WAITING_DIMENSIONS
        allow_dimensions = (
            current_mode == DialogMode.CNC_CALC_MODE and 
            current_state == DialogState.WAITING_DIMENSIONS
        )
        
        # Извлекаем данные из сообщения с учетом контекста
        extracted_data = self.validator.extract_data_from_message(
            message,
            allow_dimensions=allow_dimensions,
            has_standard=has_standard
        )
        
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
                    'mode': DialogMode.CNC_CALC_MODE,
                    'intent': Intent.UNKNOWN,
                    'metadata': {'no_work_number_required': True}
                }
            else:
                return {
                    'response': "Не понял операцию. Укажите: токарка, фрезеровка, сверление или нарезка.",
                    'state': current_state,
                    'mode': current_mode,
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
                    'mode': DialogMode.CNC_CALC_MODE,
                    'intent': Intent.UNKNOWN,
                    'metadata': {'no_work_number_required': True}
                }
            else:
                return {
                    'response': "Не понял материал. Укажите: алюминий, сталь, титан, медь...",
                    'state': current_state,
                    'mode': current_mode,
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
                        'mode': DialogMode.CNC_CALC_MODE,
                        'intent': Intent.UNKNOWN,
                        'metadata': {
                            'context': context.to_dict(),
                            'no_work_number_required': True
                        }
                    }
            else:
                return {
                    'response': "Не понял размеры. Укажите диапазон (например: 50 до 200) или диаметр (Ø50).",
                    'state': current_state,
                    'mode': current_mode,
                    'intent': Intent.UNKNOWN,
                    'metadata': {}
                }
        
        # Для остальных состояний возвращаем стандартный ответ
        return {
            'response': "Не понял. Напишите 'помощь' для справки или 'сброс' для начала заново.",
            'state': current_state,
            'mode': current_mode,
            'intent': Intent.UNKNOWN,
            'metadata': {}
        }
