"""
RequirementEngine — превращает StandardEntity в ManufacturingRequirement.
Определяет точность, класс обработки, критичность.
Использует математические вычисления для точных значений допусков.
"""

from typing import Optional
import logging

from standards.models import StandardEntity, ManufacturingRequirement
from standards.calculations.tolerance_calculator import (
    calculate_it_tolerance,
    calculate_tolerance_field_values,
)
from standards.calculations.thread_geometry import (
    calculate_thread_geometry,
    get_thread_tolerance_requirements,
)
from standards.calculations.fit_calculator import calculate_fit
from standards.calculations.surface_roughness import (
    get_manufacturing_requirements_from_roughness,
)

logger = logging.getLogger(__name__)


class RequirementEngine:
    """
    Построение производственного требования из сущности стандарта.
    """

    def build_requirement(self, standard_entity: StandardEntity) -> Optional[ManufacturingRequirement]:
        """
        StandardEntity → ManufacturingRequirement.
        По категории сущности заполняем поля требования.
        """
        if not standard_entity:
            return None
        cat = standard_entity.category
        data = standard_entity.normalized_data

        if cat == "thread":
            return self._requirement_from_thread(standard_entity, data)
        if cat == "tolerance":
            return self._requirement_from_tolerance(standard_entity, data)
        if cat == "fit":
            return self._requirement_from_fit(standard_entity, data)
        if cat == "surface":
            return self._requirement_from_surface(standard_entity, data)
        return None

    def _requirement_from_thread(self, entity: StandardEntity, data: dict) -> ManufacturingRequirement:
        """Построить требование из резьбы с вычислением геометрии."""
        diameter = data.get("diameter")
        pitch = data.get("pitch")
        tolerance_class = data.get("tolerance_class")
        
        # Вычисляем геометрию резьбы
        thread_geometry = None
        if diameter and pitch:
            try:
                thread_geometry = calculate_thread_geometry(diameter, pitch)
            except Exception as e:
                logger.warning(f"Failed to calculate thread geometry: {e}")
        
        # Определяем требования к точности
        thread_requirements = {}
        if pitch and tolerance_class:
            try:
                thread_requirements = get_thread_tolerance_requirements(pitch, tolerance_class)
            except Exception as e:
                logger.warning(f"Failed to get thread requirements: {e}")
        
        # Определяем критичность на основе шага и класса допуска
        criticality = 2
        if pitch and pitch < 2.0:
            criticality = 3  # Мелкий шаг требует большей точности
        if tolerance_class:
            class_num = None
            for char in tolerance_class:
                if char.isdigit():
                    class_num = int(char)
                    break
            if class_num and class_num <= 6:
                criticality = 3
        
        req = ManufacturingRequirement(
            thread_diameter=diameter,
            thread_pitch=pitch,
            thread_tolerance_class=tolerance_class,
            criticality_level=criticality,
            source_entity_id=entity.id,
        )
        
        # Сохраняем вычисленную геометрию в метаданные
        if thread_geometry:
            req.metadata = {
                "thread_depth": thread_geometry.thread_depth,
                "pitch_diameter": thread_geometry.pitch_diameter,
                "minor_diameter": thread_geometry.minor_diameter,
                "requires_finish_pass": thread_requirements.get("requires_finish_pass", False),
                "min_passes": thread_requirements.get("min_passes", 1),
            }
        
        return req

    def _requirement_from_tolerance(self, entity: StandardEntity, data: dict) -> ManufacturingRequirement:
        """Построить требование из допуска с точным вычислением значения."""
        grade = data.get("tolerance_grade")
        field = data.get("tolerance_field")
        nominal = data.get("nominal_mm")
        
        # Вычисляем точное значение допуска по формуле ISO 286
        tolerance_mm = None
        tolerance_values = None
        
        if nominal and grade:
            try:
                tolerance_mm = calculate_it_tolerance(nominal, grade)
            except Exception as e:
                logger.warning(f"Failed to calculate IT tolerance: {e}")
        
        if nominal and field:
            try:
                tolerance_values = calculate_tolerance_field_values(nominal, field, grade)
                if tolerance_mm is None:
                    tolerance_mm = tolerance_values.get("tolerance_mm")
            except Exception as e:
                logger.warning(f"Failed to calculate tolerance field values: {e}")
        
        # Определяем критичность
        criticality = 2
        if grade and grade <= 7:
            criticality = 3
        if tolerance_mm and tolerance_mm <= 0.01:
            criticality = 4  # Очень малый допуск
        
        req = ManufacturingRequirement(
            tolerance_grade=grade,
            tolerance_field=field,
            dimensional_tolerance=tolerance_mm,
            criticality_level=criticality,
            source_entity_id=entity.id,
        )
        
        # Сохраняем полные значения допуска в метаданные
        if tolerance_values:
            req.metadata = {
                "upper_deviation_mm": tolerance_values.get("upper_deviation_mm"),
                "lower_deviation_mm": tolerance_values.get("lower_deviation_mm"),
                "max_size_mm": tolerance_values.get("max_size_mm"),
                "min_size_mm": tolerance_values.get("min_size_mm"),
            }
        
        return req

    def _requirement_from_fit(self, entity: StandardEntity, data: dict) -> ManufacturingRequirement:
        """Построить требование из посадки с вычислением зазоров/натягов."""
        fit_type = data.get("fit_type")
        hole_field = data.get("hole")
        shaft_field = data.get("shaft")
        nominal = data.get("nominal_mm")
        
        # Вычисляем параметры посадки
        fit_data = None
        if nominal and hole_field and shaft_field:
            try:
                fit_data = calculate_fit(nominal, hole_field, shaft_field)
                if fit_type is None:
                    fit_type = fit_data.get("fit_type")
            except Exception as e:
                logger.warning(f"Failed to calculate fit: {e}")
        
        # Определяем критичность
        criticality = 2
        if fit_type == "interference":
            criticality = 4  # Посадка с натягом требует особого внимания
        elif fit_type == "transition":
            criticality = 3  # Переходная посадка требует повышенной точности
        
        req = ManufacturingRequirement(
            fit_type=fit_type,
            fit_hole=hole_field,
            fit_shaft=shaft_field,
            criticality_level=criticality,
            source_entity_id=entity.id,
        )
        
        # Сохраняем вычисленные параметры посадки
        if fit_data:
            req.metadata = {
                "min_clearance_mm": fit_data.get("min_clearance_mm"),
                "max_clearance_mm": fit_data.get("max_clearance_mm"),
                "hole_tolerance_mm": fit_data.get("hole_tolerance_mm"),
                "shaft_tolerance_mm": fit_data.get("shaft_tolerance_mm"),
            }
        
        return req

    def _requirement_from_surface(self, entity: StandardEntity, data: dict) -> ManufacturingRequirement:
        """Построить требование из шероховатости с вычислением требований к обработке."""
        ra = data.get("ra_um")
        rz = data.get("rz_um")
        
        # Ra приоритетнее; при только Rz можно приблизить Ra
        surface_roughness = ra if ra is not None else (rz / 4.0 if rz else None)  # грубо Rz≈4Ra
        
        # Получаем производственные требования на основе шероховатости
        roughness_requirements = {}
        if surface_roughness:
            try:
                roughness_requirements = get_manufacturing_requirements_from_roughness(surface_roughness)
            except Exception as e:
                logger.warning(f"Failed to get roughness requirements: {e}")
        
        # Определяем критичность
        criticality = 1
        if surface_roughness:
            if surface_roughness <= 0.4:
                criticality = 4  # Суперфиниш
            elif surface_roughness <= 1.6:
                criticality = 3  # Чистовая обработка
            elif surface_roughness <= 3.2:
                criticality = 2  # Получистовая
        
        req = ManufacturingRequirement(
            surface_roughness=surface_roughness,
            criticality_level=criticality,
            source_entity_id=entity.id,
        )
        
        # Сохраняем требования к обработке
        if roughness_requirements:
            req.metadata = {
                "requires_finish_pass": roughness_requirements.get("requires_finish_pass", False),
                "max_feed_reduction": roughness_requirements.get("max_feed_reduction", 1.0),
                "surface_quality": roughness_requirements.get("surface_quality", "standard"),
            }
        
        return req
