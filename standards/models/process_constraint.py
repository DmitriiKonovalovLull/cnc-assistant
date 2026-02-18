"""
ProcessConstraint — ограничение технологии, выведенное из ManufacturingRequirement.
Используется constraint_engine и передаётся в process_planner.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ProcessConstraint:
    """
    Ограничение для маршрута обработки.
    Идентификатор constraint_id — машинный ключ для применения в плане.
    """
    constraint_id: str  # finish_turning_required, low_feed_required, thermal_control_required, ...
    description: Optional[str] = None  # человекочитаемое описание
    parameters: Optional[dict] = None  # доп. параметры (например min_ra, max_feed)
    source_requirement_id: Optional[str] = None
