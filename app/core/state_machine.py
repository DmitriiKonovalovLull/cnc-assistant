"""
FSM - Машина состояний для CNC Assistant.
Состояния: EMPTY → PARTIAL → ASSUMED → READY → CALCULATED → FEEDBACK
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """
    Состояния системы обработки задачи.
    """
    EMPTY = "empty"  # Нет данных
    PARTIAL = "partial"  # Частичные данные
    ASSUMED = "assumed"  # Данные с предположениями
    READY = "ready"  # Достаточно данных для расчета
    CALCULATED = "calculated"  # Расчет выполнен
    FEEDBACK = "feedback"  # Получена обратная связь от оператора


@dataclass
class StateTransition:
    """Переход между состояниями."""
    from_state: SystemState
    to_state: SystemState
    condition: str
    required_fields: List[str]


class StateMachine:
    """
    Машина состояний для определения готовности к расчету.
    """
    
    def __init__(self):
        """Инициализация машины состояний."""
        self.current_state = SystemState.EMPTY
    
    def determine_state(self, context: 'Context') -> SystemState:
        """
        Определить текущее состояние на основе контекста.
        
        Args:
            context: Контекст задачи
            
        Returns:
            Текущее состояние системы
        """
        # Обязательные поля для расчета
        required_fields = ['material', 'diameter_start', 'diameter_end']
        
        # Проверяем наличие обязательных полей
        missing_fields = []
        for field in required_fields:
            if not context.is_field_set(field):
                missing_fields.append(field)
        
        # Если все обязательные поля есть
        if not missing_fields:
            # Проверяем, есть ли предположения
            if context.assumptions_made:
                return SystemState.ASSUMED
            else:
                return SystemState.READY
        
        # Если есть хотя бы одно поле
        has_any_field = any(
            context.is_field_set(field) 
            for field in ['material', 'diameter_start', 'diameter_end', 'machine_type', 'tool_name']
        )
        
        if has_any_field:
            return SystemState.PARTIAL
        else:
            return SystemState.EMPTY
    
    def can_calculate(self, context: 'Context') -> bool:
        """
        Проверить, можно ли выполнить расчет.
        
        Args:
            context: Контекст задачи
            
        Returns:
            True если можно рассчитывать
        """
        state = self.determine_state(context)
        return state in [SystemState.READY, SystemState.ASSUMED]
    
    def needs_clarification(self, context: 'Context') -> List[str]:
        """
        Определить, какие поля нужно уточнить.
        
        Args:
            context: Контекст задачи
            
        Returns:
            Список полей, которые нужно уточнить
        """
        required_fields = ['material', 'diameter_start', 'diameter_end']
        missing = []
        
        for field in required_fields:
            if not context.is_field_set(field):
                missing.append(field)
        
        return missing
    
    def transition_to_calculated(self) -> None:
        """Переход в состояние CALCULATED после расчета."""
        if self.current_state in [SystemState.READY, SystemState.ASSUMED]:
            self.current_state = SystemState.CALCULATED
            logger.info(f"State transition: {SystemState.READY} → {SystemState.CALCULATED}")
    
    def transition_to_feedback(self) -> None:
        """Переход в состояние FEEDBACK после получения обратной связи."""
        if self.current_state == SystemState.CALCULATED:
            self.current_state = SystemState.FEEDBACK
            logger.info(f"State transition: {SystemState.CALCULATED} → {SystemState.FEEDBACK}")
    
    def reset(self) -> None:
        """Сброс состояния."""
        self.current_state = SystemState.EMPTY
        logger.info("State machine reset to EMPTY")
