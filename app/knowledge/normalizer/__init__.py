"""
Нормализаторы для различных сущностей системы.
"""

from app.knowledge.normalizer.material_map import MaterialNormalizer
from app.knowledge.normalizer.tool_map import ToolNormalizer
from app.knowledge.normalizer.machine_map import MachineNormalizer

__all__ = [
    'MaterialNormalizer',
    'ToolNormalizer',
    'MachineNormalizer'
]
