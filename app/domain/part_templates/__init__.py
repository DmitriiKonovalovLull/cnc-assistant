"""
Шаблоны деталей - инженерная логика для типовых деталей.
Работает БЕЗ ГОСТов - это общие шаблоны для классов деталей.
"""

from app.domain.part_templates.bolt import BOLT_TEMPLATE
from app.domain.part_templates.screw import SCREW_TEMPLATE
from app.domain.part_templates.stud import STUD_TEMPLATE
from app.domain.part_templates.shaft import SHAFT_TEMPLATE
from app.domain.part_templates.bushing import BUSHING_TEMPLATE
from app.domain.part_templates.nut import NUT_TEMPLATE

# Словарь шаблонов по типам деталей
PART_TEMPLATES = {
    'bolt': BOLT_TEMPLATE,
    'screw': SCREW_TEMPLATE,
    'stud': STUD_TEMPLATE,
    'shaft': SHAFT_TEMPLATE,
    'bushing': BUSHING_TEMPLATE,
    'nut': NUT_TEMPLATE,
}


def get_template(part_type: str) -> dict:
    """
    Получить шаблон детали по типу.
    
    Args:
        part_type: Тип детали (bolt, screw, stud, shaft, bushing)
        
    Returns:
        Шаблон детали или пустой словарь
    """
    return PART_TEMPLATES.get(part_type, {})
