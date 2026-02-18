"""
ConstraintEngine — превращает ManufacturingRequirement в ограничения технологии.
Использует математические вычисления для определения точных ограничений.
Используется process_planner для применения к маршруту.
"""

from typing import List
import logging

from standards.models import ManufacturingRequirement, ProcessConstraint
from standards.calculations.tolerance_calculator import (
    get_manufacturing_requirements_from_tolerance,
)
from standards.calculations.fit_calculator import (
    get_manufacturing_requirements_from_fit,
)
from standards.calculations.surface_roughness import (
    get_manufacturing_requirements_from_roughness,
    calculate_feed_from_roughness,
)
from standards.calculations.thread_geometry import (
    get_thread_tolerance_requirements,
)

logger = logging.getLogger(__name__)


class ConstraintEngine:
    """
    Генерация технологических ограничений по производственному требованию.
    """

    def generate_constraints(self, requirement: ManufacturingRequirement) -> List[ProcessConstraint]:
        """
        Требование → список ограничений для плана обработки.
        Использует математические вычисления для определения точных ограничений.
        """
        if not requirement:
            return []
        out: List[ProcessConstraint] = []

        # 1. Обработка допусков
        if requirement.dimensional_tolerance is not None:
            try:
                tolerance_reqs = get_manufacturing_requirements_from_tolerance(
                    requirement.dimensional_tolerance
                )
                
                if tolerance_reqs.get("requires_finish"):
                    out.append(ProcessConstraint(
                        constraint_id="finish_turning_required",
                        description=f"Требуется чистовая обработка (допуск {requirement.dimensional_tolerance:.4f} мм)",
                        parameters={
                            "tolerance_mm": requirement.dimensional_tolerance,
                            "max_feed_reduction": tolerance_reqs.get("max_feed_reduction", 1.0),
                        },
                        source_requirement_id=requirement.source_entity_id,
                    ))
                
                if tolerance_reqs.get("requires_grinding"):
                    out.append(ProcessConstraint(
                        constraint_id="grinding_required",
                        description=f"Требуется шлифование (допуск {requirement.dimensional_tolerance:.4f} мм)",
                        parameters={"tolerance_mm": requirement.dimensional_tolerance},
                        source_requirement_id=requirement.source_entity_id,
                    ))
                
                if tolerance_reqs.get("requires_superfinish"):
                    out.append(ProcessConstraint(
                        constraint_id="superfinish_required",
                        description=f"Требуется суперфиниш (допуск {requirement.dimensional_tolerance:.4f} мм)",
                        parameters={"tolerance_mm": requirement.dimensional_tolerance},
                        source_requirement_id=requirement.source_entity_id,
                    ))
            except Exception as e:
                logger.warning(f"Failed to generate tolerance constraints: {e}")
        
        # Альтернатива: если есть только класс допуска без значения
        elif requirement.tolerance_grade is not None and requirement.tolerance_grade <= 7:
            out.append(ProcessConstraint(
                constraint_id="finish_turning_required",
                description=f"Требуется чистовая обработка (допуск IT{requirement.tolerance_grade})",
                parameters={"max_it_grade": requirement.tolerance_grade},
                source_requirement_id=requirement.source_entity_id,
            ))

        # 2. Обработка шероховатости
        if requirement.surface_roughness is not None:
            try:
                roughness_reqs = get_manufacturing_requirements_from_roughness(
                    requirement.surface_roughness
                )
                
                # Вычисляем максимальную подачу для достижения шероховатости
                # (требует знания радиуса инструмента, используем типичное значение)
                typical_tool_radius = 0.8  # мм
                max_feed = calculate_feed_from_roughness(
                    requirement.surface_roughness,
                    typical_tool_radius
                )
                
                out.append(ProcessConstraint(
                    constraint_id="surface_roughness_limit",
                    description=f"Ограничение подачи для Ra {requirement.surface_roughness} мкм",
                    parameters={
                        "max_ra_um": requirement.surface_roughness,
                        "max_feed_mm_rev": max_feed,
                        "max_feed_reduction": roughness_reqs.get("max_feed_reduction", 1.0),
                        "requires_finish_pass": roughness_reqs.get("requires_finish_pass", False),
                    },
                    source_requirement_id=requirement.source_entity_id,
                ))
            except Exception as e:
                logger.warning(f"Failed to generate roughness constraints: {e}")

        # 3. Обработка посадок
        if requirement.fit_type == "interference":
            # Вычисляем требования для посадки с натягом
            if requirement.fit_hole and requirement.fit_shaft:
                # Нужен номинальный диаметр из метаданных или контекста
                # Для примера используем значение по умолчанию
                try:
                    # Пытаемся получить из метаданных
                    nominal = requirement.metadata.get("nominal_diameter_mm") if requirement.metadata else None
                    if nominal:
                        from standards.calculations.fit_calculator import calculate_fit
                        fit_data = calculate_fit(nominal, requirement.fit_hole, requirement.fit_shaft)
                        fit_reqs = get_manufacturing_requirements_from_fit(fit_data)
                        
                        out.append(ProcessConstraint(
                            constraint_id="thermal_control_required",
                            description="Посадка с натягом — контроль температуры/сборки",
                            parameters={
                                "fit_type": "interference",
                                "requires_heating": fit_reqs.get("requires_heating", False),
                                "assembly_method": fit_reqs.get("assembly_method", "press_fit"),
                            },
                            source_requirement_id=requirement.source_entity_id,
                        ))
                    else:
                        # Базовое ограничение без вычислений
                        out.append(ProcessConstraint(
                            constraint_id="thermal_control_required",
                            description="Посадка с натягом — контроль температуры/сборки",
                            source_requirement_id=requirement.source_entity_id,
                        ))
                except Exception as e:
                    logger.warning(f"Failed to generate fit constraints: {e}")
            else:
                out.append(ProcessConstraint(
                    constraint_id="thermal_control_required",
                    description="Посадка с натягом — контроль температуры/сборки",
                    source_requirement_id=requirement.source_entity_id,
                ))

        # 4. Обработка резьбы
        if requirement.thread_pitch is not None:
            try:
                tolerance_class = requirement.thread_tolerance_class or "6g"
                thread_reqs = get_thread_tolerance_requirements(
                    requirement.thread_pitch,
                    tolerance_class
                )
                
                out.append(ProcessConstraint(
                    constraint_id="thread_operation_required",
                    description=f"Требуется нарезка резьбы M{requirement.thread_diameter}x{requirement.thread_pitch}-{tolerance_class}",
                    parameters={
                        "pitch": requirement.thread_pitch,
                        "diameter": requirement.thread_diameter,
                        "tolerance_class": tolerance_class,
                        "requires_finish_pass": thread_reqs.get("requires_finish_pass", False),
                        "min_passes": thread_reqs.get("min_passes", 1),
                        "max_feed_mm_rev": thread_reqs.get("max_feed_mm_rev"),
                    },
                    source_requirement_id=requirement.source_entity_id,
                ))
            except Exception as e:
                logger.warning(f"Failed to generate thread constraints: {e}")

        return out
