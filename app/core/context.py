"""
КОНТЕКСТ - ЕДИНЫЙ ОБЪЕКТ СОСТОЯНИЯ.
Сердце системы: хранит что известно точно, что предположено, что по умолчанию.
НИ ОДИН МОДУЛЬ не хранит состояние сам - всё через Context.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Источник данных."""
    USER = "user"  # Пользователь указал явно
    ASSUMED = "assumed"  # Система предположила
    DEFAULT = "default"  # Значение по умолчанию
    INFERRED = "inferred"  # Выведено из других данных
    EXTERNAL = "external"  # Данные из внешних источников (интернет, БД и т.д.)


@dataclass
class FieldMetadata:
    """Метаданные поля контекста."""
    value: Any
    source: DataSource
    confidence: float  # 0.0 - 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    reasoning: Optional[str] = None  # Почему такое значение


@dataclass
class Context:
    """
    Единый объект состояния системы.
    Хранит все данные о текущей задаче обработки.
    """
    
    # ========== ОСНОВНЫЕ ДАННЫЕ ==========
    
    # Материал
    material: Optional[str] = None
    material_metadata: Optional[FieldMetadata] = None
    
    # Операция
    operation: Optional[str] = None  # токарка, фрезерование
    operation_metadata: Optional[FieldMetadata] = None
    
    # Режим обработки
    mode: Optional[str] = None  # черновая, получистовая, чистовая
    mode_metadata: Optional[FieldMetadata] = None
    
    # Геометрия
    diameter_start: Optional[float] = None  # мм
    diameter_end: Optional[float] = None  # мм
    length: Optional[float] = None  # мм
    geometry_metadata: Optional[FieldMetadata] = None
    
    # Станок
    machine_type: Optional[str] = None  # токарный ЧПУ, ручной и т.д.
    machine_power: Optional[float] = None  # кВт
    machine_max_rpm: Optional[float] = None
    machine_metadata: Optional[FieldMetadata] = None
    
    # Инструмент
    tool_material: Optional[str] = None  # твердый сплав, быстрорез
    tool_radius: Optional[float] = None  # мм (радиус при вершине)
    tool_diameter: Optional[float] = None  # мм (диаметр державки/фрезы)
    tool_overhang: Optional[float] = None  # мм (вылет инструмента)
    tool_type: Optional[str] = None  # проходной, чистовой
    tool_name: Optional[str] = None  # CNMG 120408, WNMG и т.д.
    tool_display_name: Optional[str] = None  # Пользовательское имя: "Мой черновой", "Резец для титана"
    tool_manufacturer: Optional[str] = None  # SANDVIK, KENNAMETAL и т.д.
    tool_grade: Optional[str] = None  # P25, M15 и т.д.
    tool_metadata: Optional[FieldMetadata] = None
    
    # Стандартные детали (ГОСТ/ОСТ/DIN/ISO)
    standard_id: Optional[str] = None  # ГОСТ_7798-30, ОСТ_1_31102-80
    pending_standard_search: Optional[str] = None  # Ожидаем "да" на поиск: "ОСТ 30560-80"
    pending_standard_apply: Optional[str] = None  # standard_id — ждём "номер работы" или "Новая"
    part_type: Optional[str] = None  # болт, винт, шпилька, вал, втулка, гайка
    thread_size: Optional[str] = None  # M6, M12, M16 и т.д.
    quantity: Optional[int] = None  # Количество деталей
    collecting_params: bool = False  # Флаг сбора параметров для стандартной детали
    standard_metadata: Optional[FieldMetadata] = None
    
    # ========== РЕЗУЛЬТАТЫ РАСЧЁТОВ ==========
    
    # Рекомендации калькулятора
    recommended_vc: Optional[float] = None  # м/мин
    recommended_rpm: Optional[float] = None  # об/мин
    recommended_feed: Optional[float] = None  # мм/об
    recommended_ap: Optional[float] = None  # мм
    recommended_power: Optional[float] = None  # кВт
    
    # Стратегия проходов
    passes_strategy: Optional[List[Dict[str, Any]]] = None
    
    # ========== МЕТАДАННЫЕ ==========
    
    # История диалога
    dialog_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Уровень уверенности системы
    overall_confidence: float = 0.0  # 0.0 - 1.0
    
    # Что было предположено
    assumptions_made: List[str] = field(default_factory=list)
    
    # Что было установлено по умолчанию
    defaults_used: List[str] = field(default_factory=list)
    
    # Пользовательские данные
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    lang: Optional[str] = None  # ru, en, zh — язык интерфейса

    # ========== МЕТОДЫ ==========
    
    def set_field(
        self,
        field_name: str,
        value: Any,
        source: DataSource,
        confidence: float = 1.0,
        reasoning: Optional[str] = None
    ) -> None:
        """Установить значение поля с метаданными."""
        if not 0.0 <= confidence <= 1.0:
            confidence = max(0.0, min(1.0, confidence))
        
        metadata = FieldMetadata(
            value=value,
            source=source,
            confidence=confidence,
            reasoning=reasoning
        )
        
        # Устанавливаем значение
        setattr(self, field_name, value)
        setattr(self, f"{field_name}_metadata", metadata)
        
        # Обновляем списки
        if source == DataSource.ASSUMED:
            if field_name not in self.assumptions_made:
                self.assumptions_made.append(field_name)
        elif source == DataSource.DEFAULT:
            if field_name not in self.defaults_used:
                self.defaults_used.append(field_name)
        
        # Пересчитываем общую уверенность
        self._update_confidence()
    
    def get_field_metadata(self, field_name: str) -> Optional[FieldMetadata]:
        """Получить метаданные поля."""
        return getattr(self, f"{field_name}_metadata", None)
    
    def is_field_set(self, field_name: str) -> bool:
        """Проверить, установлено ли поле."""
        value = getattr(self, field_name, None)
        return value is not None
    
    def is_field_from_user(self, field_name: str) -> bool:
        """Проверить, установлено ли поле пользователем."""
        metadata = self.get_field_metadata(field_name)
        return metadata is not None and metadata.source == DataSource.USER
    
    def reset_temp(self) -> None:
        """
        Сбросить временные данные сессии.
        Очищает временные флаги и ожидания, но сохраняет основные данные.
        """
        self.pending_standard_search = None
        self.pending_standard_apply = None
        self.collecting_params = False
        # Очищаем временные данные, но сохраняем основные (material, machine_type и т.д.)
        logger.debug("Temporary session data reset")
    
    def clear_current_object(self) -> None:
        """
        Очистить текущий объект из сессии.
        Используется при отмене операции.
        """
        # Очищаем данные о стандартной детали
        self.standard_id = None
        self.part_type = None
        self.thread_size = None
        self.quantity = None
        self.collecting_params = False
        self.pending_standard_search = None
        self.pending_standard_apply = None
        # Очищаем результаты расчетов
        self.recommended_vc = None
        self.recommended_rpm = None
        self.recommended_feed = None
        self.recommended_ap = None
        self.recommended_power = None
        self.passes_strategy = None
        logger.debug("Current object cleared from session")
    
    def get_missing_fields(self, required_fields: List[str]) -> List[str]:
        """Получить список недостающих обязательных полей."""
        missing = []
        for field_name in required_fields:
            if not self.is_field_set(field_name):
                missing.append(field_name)
        return missing
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать контекст в словарь."""
        result = {}
        
        # Основные поля
        for field_name in [
            'material', 'operation', 'mode',
            'diameter_start', 'diameter_end', 'length',
            'machine_type', 'machine_power', 'machine_max_rpm',
            'tool_material', 'tool_radius', 'tool_diameter', 'tool_overhang', 'tool_type',
            'tool_name', 'tool_display_name', 'tool_manufacturer', 'tool_grade',
            'standard_id', 'pending_standard_search', 'pending_standard_apply', 'part_type', 'thread_size', 'quantity', 'collecting_params',
            'recommended_vc', 'recommended_rpm', 'recommended_feed',
            'recommended_ap', 'recommended_power',
            'overall_confidence', 'user_id', 'session_id', 'lang'
        ]:
            value = getattr(self, field_name, None)
            if value is not None:
                result[field_name] = value
        
        # Метаданные
        result['assumptions_made'] = self.assumptions_made
        result['defaults_used'] = self.defaults_used
        result['dialog_history'] = self.dialog_history
        
        # Метаданные полей
        metadata_dict = {}
        for field_name in [
            'material', 'operation', 'mode', 'geometry',
            'machine', 'tool'
        ]:
            metadata = self.get_field_metadata(field_name)
            if metadata:
                metadata_dict[field_name] = {
                    'source': metadata.source.value,
                    'confidence': metadata.confidence,
                    'reasoning': metadata.reasoning
                }
        if metadata_dict:
            result['field_metadata'] = metadata_dict
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Context':
        """Создать контекст из словаря."""
        context = cls()
        
        # Основные поля
        for field_name in [
            'material', 'operation', 'mode',
            'diameter_start', 'diameter_end', 'length',
            'machine_type', 'machine_power', 'machine_max_rpm',
            'tool_material', 'tool_radius', 'tool_diameter', 'tool_overhang', 'tool_type',
            'tool_name', 'tool_display_name', 'tool_manufacturer', 'tool_grade',
            'standard_id', 'pending_standard_search', 'pending_standard_apply', 'part_type', 'thread_size', 'quantity', 'collecting_params',
            'recommended_vc', 'recommended_rpm', 'recommended_feed',
            'recommended_ap', 'recommended_power',
            'overall_confidence', 'user_id', 'session_id', 'lang'
        ]:
            if field_name in data:
                setattr(context, field_name, data[field_name])
        
        # Списки
        context.assumptions_made = data.get('assumptions_made', [])
        context.defaults_used = data.get('defaults_used', [])
        context.dialog_history = data.get('dialog_history', [])
        
        return context
    
    def add_to_history(self, event: str, data: Dict[str, Any]) -> None:
        """Добавить событие в историю диалога."""
        self.dialog_history.append({
            'timestamp': datetime.now().isoformat(),
            'event': event,
            'data': data
        })
    
    def _update_confidence(self) -> None:
        """Пересчитать общую уверенность системы."""
        metadata_fields = [
            self.material_metadata,
            self.operation_metadata,
            self.mode_metadata,
            self.geometry_metadata,
            self.machine_metadata,
            self.tool_metadata
        ]
        
        valid_metadata = [m for m in metadata_fields if m is not None]
        
        if not valid_metadata:
            self.overall_confidence = 0.0
            return
        
        # Средняя уверенность по всем полям
        avg_confidence = sum(m.confidence for m in valid_metadata) / len(valid_metadata)
        
        # Штраф за предположения
        assumption_penalty = len(self.assumptions_made) * 0.1
        default_penalty = len(self.defaults_used) * 0.05
        
        self.overall_confidence = max(0.0, min(1.0, avg_confidence - assumption_penalty - default_penalty))
    
    def get_summary(self) -> str:
        """Получить текстовую сводку контекста."""
        lines = []
        
        if self.material:
            source = self.material_metadata.source.value if self.material_metadata else "unknown"
            lines.append(f"Материал: {self.material} ({source})")
        
        if self.operation:
            source = self.operation_metadata.source.value if self.operation_metadata else "unknown"
            lines.append(f"Операция: {self.operation} ({source})")
        
        if self.diameter_start and self.diameter_end:
            lines.append(f"Диаметры: Ø{self.diameter_start} → Ø{self.diameter_end} мм")
        
        if self.machine_type:
            lines.append(f"Станок: {self.machine_type}")
        
        if self.assumptions_made:
            lines.append(f"Предположения: {', '.join(self.assumptions_made)}")
        
        if self.defaults_used:
            lines.append(f"По умолчанию: {', '.join(self.defaults_used)}")
        
        lines.append(f"Уверенность: {self.overall_confidence:.0%}")
        
        return "\n".join(lines) if lines else "Контекст пуст"
