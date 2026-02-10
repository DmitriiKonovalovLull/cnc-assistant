"""
ДВИГАТЕЛЬ ПРЕДПОЛОЖЕНИЙ - магия ИИ.
Делает разумные предположения на основе контекста.
Всегда помечает source=ASSUMED и confidence=0.0-1.0
"""

from typing import Dict, Any, Optional
from app.core.context import Context, DataSource


class AssumptionEngine:
    """
    Двигатель предположений.
    Делает разумные предположения на основе контекста.
    """
    
    def __init__(self, knowledge_service=None):
        """
        Инициализация двигателя предположений.
        
        Args:
            knowledge_service: Сервис знаний (опционально)
        """
        self.knowledge_service = knowledge_service
    
    def make_assumptions(self, context: Context) -> Context:
        """
        Сделать предположения для контекста.
        
        ВАЖНО: Предположения делаются ТОЛЬКО для инженерных запросов.
        Не делаем предположения для приветствий, команд и т.д.
        
        Args:
            context: Контекст для анализа
            
        Returns:
            Обновленный контекст
        """
        # Проверяем, есть ли хотя бы минимальные данные для инженерного запроса
        # Если нет материала и диаметров - не делаем предположения
        has_minimal_data = (
            context.is_field_set('material') or
            context.is_field_set('diameter_start') or
            context.is_field_set('operation') or
            context.is_field_set('standard_id')  # Для стандартных деталей
        )
        
        if not has_minimal_data:
            # Нет минимальных данных - не делаем предположения
            return context
        
        # 1. Предположения о станке
        if not context.is_field_set('machine_type'):
            assumed_machine = self._assume_machine_type(context)
            if assumed_machine:
                context.set_field(
                    'machine_type',
                    assumed_machine,
                    DataSource.ASSUMED,
                    confidence=0.7,
                    reasoning="Предположено на основе операции"
                )
        
        if not context.is_field_set('machine_power'):
            assumed_power = self._assume_machine_power(context)
            if assumed_power:
                context.set_field(
                    'machine_power',
                    assumed_power,
                    DataSource.ASSUMED,
                    confidence=0.6,
                    reasoning="Типичная мощность для данного типа станка"
                )
        
        # 2. Предположения об инструменте
        if not context.is_field_set('tool_material'):
            assumed_tool = self._assume_tool_material(context)
            if assumed_tool:
                context.set_field(
                    'tool_material',
                    assumed_tool,
                    DataSource.ASSUMED,
                    confidence=0.8,
                    reasoning="Типичный инструмент для данного типа станка"
                )
        
        if not context.is_field_set('tool_radius'):
            assumed_radius = self._assume_tool_radius(context)
            if assumed_radius:
                context.set_field(
                    'tool_radius',
                    assumed_radius,
                    DataSource.ASSUMED,
                    confidence=0.7,
                    reasoning="Типичный радиус для данного типа обработки"
                )
        
        if not context.is_field_set('tool_overhang'):
            assumed_overhang = self._assume_tool_overhang(context)
            if assumed_overhang:
                context.set_field(
                    'tool_overhang',
                    assumed_overhang,
                    DataSource.ASSUMED,
                    confidence=0.6,
                    reasoning="Типичный вылет для данного типа обработки"
                )
        
        # 3. Предположения о режиме обработки (только если есть диаметры)
        if not context.is_field_set('mode') and (context.diameter_start and context.diameter_end):
            assumed_mode = self._assume_mode(context)
            if assumed_mode:
                context.set_field(
                    'mode',
                    assumed_mode,
                    DataSource.ASSUMED,
                    confidence=0.7,
                    reasoning="Предположено на основе припуска"
                )
        
        # 4. Предположения о длине
        if not context.is_field_set('length'):
            assumed_length = self._assume_length(context)
            if assumed_length:
                context.set_field(
                    'length',
                    assumed_length,
                    DataSource.ASSUMED,
                    confidence=0.5,
                    reasoning="Типичная длина для данного диаметра"
                )
        
        return context
    
    def _assume_machine_type(self, context: Context) -> Optional[str]:
        """
        Предположить тип станка.
        
        ВАЖНО: Не делаем предположения без явных признаков инженерного запроса.
        """
        # Если указана операция "токарка" → токарный ЧПУ
        if context.operation == 'токарка':
            return 'токарный ЧПУ'
        
        # Если указана операция "фрезерование" → фрезерный ЧПУ
        if context.operation == 'фрезерование':
            return 'фрезерный ЧПУ'
        
        # Если есть стандарт - предполагаем токарный (большинство стандартных деталей токарные)
        if context.is_field_set('standard_id'):
            return 'токарный ЧПУ'
        
        # НЕ делаем предположение по умолчанию - это приводит к ложным срабатываниям FSM
        return None
    
    def _assume_machine_power(self, context: Context) -> Optional[float]:
        """Предположить мощность станка."""
        machine_type = context.machine_type or ''
        
        # Типичные мощности по типам станков
        power_map = {
            'токарный ЧПУ': 11.0,
            'токарный ручной': 7.5,
            'фрезерный ЧПУ': 15.0,
            'фрезерный ручной': 5.5
        }
        
        for key, power in power_map.items():
            if key in machine_type.lower():
                return power
        
        # По умолчанию
        return 11.0
    
    def _assume_tool_material(self, context: Context) -> Optional[str]:
        """Предположить материал инструмента."""
        machine_type = context.machine_type or ''
        
        # ЧПУ → твердый сплав (типично)
        if 'чпу' in machine_type.lower():
            return 'твердый сплав'
        
        # Ручной → быстрорез (типично)
        if 'ручной' in machine_type.lower():
            return 'быстрорез'
        
        # По умолчанию
        return 'твердый сплав'
    
    def _assume_tool_radius(self, context: Context) -> Optional[float]:
        """Предположить радиус инструмента."""
        mode = context.mode or ''
        
        # Чистовая → меньший радиус
        if 'чистов' in mode.lower():
            return 0.4
        
        # Черновая → больший радиус
        if 'чернов' in mode.lower():
            return 0.8
        
        # По умолчанию
        return 0.8
    
    def _assume_tool_overhang(self, context: Context) -> Optional[float]:
        """Предположить вылет инструмента."""
        # Типичный вылет для токарки
        if context.operation == 'токарка':
            return 30.0
        
        # Типичный вылет для фрезерования
        if context.operation == 'фрезерование':
            return 50.0
        
        # По умолчанию
        return 40.0
    
    def _assume_mode(self, context: Context) -> Optional[str]:
        """Предположить режим обработки на основе припуска."""
        if not context.diameter_start or not context.diameter_end:
            return 'черновая'  # По умолчанию
        
        stock = (context.diameter_start - context.diameter_end) / 2
        
        # Большой припуск → черновая
        if stock > 5.0:
            return 'черновая'
        
        # Средний припуск → получистовая
        if stock > 1.0:
            return 'получистовая'
        
        # Маленький припуск → чистовая
        return 'чистовая'
    
    def _assume_length(self, context: Context) -> Optional[float]:
        """Предположить длину обработки."""
        # Если есть диаметр, предполагаем длину пропорционально
        if context.diameter_start:
            # Типичное соотношение длина/диаметр = 1-2
            assumed_length = context.diameter_start * 1.5
            return max(20.0, min(assumed_length, 200.0))  # Ограничения
        
        # По умолчанию
        return 50.0
    
    def explain_assumption(self, field_name: str, context: Context) -> str:
        """
        Объяснить, почему было сделано предположение.
        
        Args:
            field_name: Имя поля
            context: Контекст
            
        Returns:
            Текстовое объяснение
        """
        metadata = context.get_field_metadata(field_name)
        if not metadata or metadata.source != DataSource.ASSUMED:
            return ""
        
        return metadata.reasoning or "Предположено на основе контекста"
