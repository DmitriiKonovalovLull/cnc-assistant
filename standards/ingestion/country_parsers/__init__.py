"""
Специализированные парсеры стандартов для разных стран.
Наследуются от базового StandardsParser и переопределяют методы для специфики стран.
"""

from .china_parser import ChinaStandardsParser
from .japan_parser import JapanStandardsParser
from .usa_parser import USAStandardsParser
from .germany_parser import GermanyStandardsParser
from .russia_parser import RussiaStandardsParser

__all__ = [
    "ChinaStandardsParser",
    "JapanStandardsParser",
    "USAStandardsParser",
    "GermanyStandardsParser",
    "RussiaStandardsParser",
]
