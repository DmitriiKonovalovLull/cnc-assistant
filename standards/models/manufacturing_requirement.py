"""
ManufacturingRequirement — производственное требование, выведенное из стандарта.
Все стандарты переводятся в эту модель для влияния на маршрут обработки.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ManufacturingRequirement:
    """
    Требование к изготовлению: допуски, шероховатость, резьба, посадка.
    Используется requirement_engine для перевода StandardEntity → ManufacturingRequirement.
    """
    # Размерные допуски
    dimensional_tolerance: Optional[float] = None  # мм
    tolerance_grade: Optional[int] = None  # IT6, IT7, ...
    tolerance_field: Optional[str] = None  # H7, g6, js6, ...

    # Шероховатость
    surface_roughness: Optional[float] = None  # Ra, мкм

    # Резьба
    thread_pitch: Optional[float] = None  # мм
    thread_diameter: Optional[float] = None  # мм
    thread_tolerance_class: Optional[str] = None  # 6g, 6H, ...

    # Посадка
    fit_type: Optional[str] = None  # clearance | interference | transition
    fit_hole: Optional[str] = None  # H7
    fit_shaft: Optional[str] = None  # g6

    # Критичность (1–5: низкая → высокая)
    criticality_level: int = 1

    # Ссылка на исходную сущность
    source_entity_id: Optional[str] = None
    
    # Метаданные с вычисленными значениями
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Метаданные с вычисленными значениями
    metadata: Optional[dict] = None
    
    def __post_init__(self):
        """Инициализация метаданных если не заданы."""
        if self.metadata is None:
            self.metadata = {}
