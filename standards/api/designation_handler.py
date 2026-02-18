"""
Обработка обозначения стандарта из сообщения пользователя.
Единая точка входа для handler: текст → сущность, требование, ограничения, сообщение.
"""

from typing import Optional, Dict, Any, List

from standards.registry.standard_registry import StandardRegistry
from standards.business_logic.requirement_engine import RequirementEngine
from standards.business_logic.constraint_engine import ConstraintEngine
from standards.models import StandardEntity, ManufacturingRequirement, ProcessConstraint


_registry = StandardRegistry()
_requirement_engine = RequirementEngine()
_constraint_engine = ConstraintEngine()


def process_designation(text: str) -> Optional[Dict[str, Any]]:
    """
    По тексту пользователя (например "Ø50 H7", "M42x1.5-6g", "Ra 1.6") получить:
    - entity, requirement, constraints и готовое сообщение для бота.
    
    Returns:
        None если обозначение не распознано.
        Иначе dict: message (str), entity, requirement, constraints (list).
    """
    if not text or not text.strip():
        return None
    raw = text.strip()
    # Пробуем по очереди: допуск (часто в чертежах), резьба, шероховатость
    entity = _registry.get_tolerance(designation=raw) or _registry.get_thread(raw) or _registry.get_surface(raw)
    if not entity:
        return None
    requirement = _requirement_engine.build_requirement(entity)
    if not requirement:
        return None
    constraints = _constraint_engine.generate_constraints(requirement)
    message = _format_reply(entity, requirement, constraints)
    return {
        "message": message,
        "entity": entity,
        "requirement": requirement,
        "constraints": constraints,
    }


def _format_reply(entity: StandardEntity, requirement: ManufacturingRequirement, constraints: List[ProcessConstraint]) -> str:
    """Сформировать ответ пользователю с вычисленными значениями."""
    lines = []
    metadata = requirement.metadata or {}
    
    if entity.category == "tolerance":
        grade = requirement.tolerance_grade
        field = requirement.tolerance_field or (f"IT{grade}" if grade else "")
        tolerance_mm = requirement.dimensional_tolerance
        
        lines.append(f"📐 <b>Допуск</b>: {field}")
        
        if tolerance_mm is not None:
            lines.append(f"Значение допуска: <b>{tolerance_mm:.4f} мм</b>")
        
        # Показываем вычисленные размеры если есть
        if metadata.get("max_size_mm") and metadata.get("min_size_mm"):
            lines.append(f"Размеры: {metadata['min_size_mm']:.3f}...{metadata['max_size_mm']:.3f} мм")
        
        if grade is not None and grade <= 7:
            lines.append("Требуется <b>чистовая обработка</b>.")
        if tolerance_mm and tolerance_mm <= 0.01:
            lines.append("⚠️ Очень малый допуск — возможно требуется шлифование.")
        
    elif entity.category == "thread":
        d = entity.normalized_data
        diameter = d.get('diameter')
        pitch = d.get('pitch')
        tolerance_class = d.get('tolerance_class') or ''
        
        lines.append(f"🔩 <b>Резьба</b>: M{diameter}×{pitch} {tolerance_class}")
        
        # Показываем вычисленную геометрию если есть
        if metadata.get("thread_depth"):
            lines.append(f"Глубина резьбы: <b>{metadata['thread_depth']:.3f} мм</b>")
        if metadata.get("pitch_diameter"):
            lines.append(f"Средний диаметр: <b>{metadata['pitch_diameter']:.3f} мм</b>")
        if metadata.get("min_passes"):
            lines.append(f"Минимальное количество проходов: <b>{metadata['min_passes']}</b>")
        
        if metadata.get("requires_finish_pass"):
            lines.append("Требуется <b>чистовой проход</b> для нарезки резьбы.")
        else:
            lines.append("Требуется операция нарезки резьбы по стандарту.")
        
    elif entity.category == "surface":
        ra = requirement.surface_roughness
        lines.append(f"📏 <b>Шероховатость</b>: Ra {ra} мкм")
        
        # Показываем требования к обработке
        if metadata.get("surface_quality"):
            quality_names = {
                "super_finish": "Суперфиниш",
                "high_finish": "Высокая чистота",
                "fine_finish": "Чистовая обработка",
                "semi_finish": "Получистовая",
                "rough": "Черновая",
            }
            quality = quality_names.get(metadata["surface_quality"], metadata["surface_quality"])
            lines.append(f"Качество поверхности: <b>{quality}</b>")
        
        if metadata.get("max_feed_reduction") and metadata["max_feed_reduction"] < 1.0:
            reduction_percent = int((1.0 - metadata["max_feed_reduction"]) * 100)
            lines.append(f"Требуется снижение подачи на <b>{reduction_percent}%</b>")
        
        if ra is not None and ra <= 1.6:
            lines.append("Рекомендуется <b>низкая подача</b> и чистовой проход.")
    
    elif entity.category == "fit":
        fit_type = requirement.fit_type
        fit_type_names = {
            "clearance": "Зазорная",
            "interference": "С натягом",
            "transition": "Переходная",
        }
        fit_name = fit_type_names.get(fit_type, fit_type or "Неизвестная")
        lines.append(f"🔗 <b>Посадка</b>: {fit_name}")
        
        if metadata.get("min_clearance_mm") is not None:
            clearance = metadata["min_clearance_mm"]
            if clearance < 0:
                lines.append(f"Натяг: <b>{abs(clearance):.4f} мм</b>")
            elif clearance > 0:
                lines.append(f"Минимальный зазор: <b>{clearance:.4f} мм</b>")
            else:
                lines.append("Переходная посадка (зазор ≈ 0)")
        
        if fit_type == "interference":
            lines.append("⚠️ Посадка с натягом — требуется контроль температуры при сборке.")
    
    else:
        lines.append("Требование по стандарту сформировано.")
    
    if constraints:
        lines.append("")
        lines.append("<b>Ограничения технологии:</b>")
        for c in constraints:
            if c.description:
                lines.append(f"• {c.description}")
    
    return "\n".join(lines)


def get_constraints_for_planner(requirement: ManufacturingRequirement) -> List[ProcessConstraint]:
    """
    Для process_planner: по требованию получить список ограничений.
    apply_to_operation_plan(constraint) для каждого.
    """
    return _constraint_engine.generate_constraints(requirement)
