"""
StandardEntity — сущность стандарта после нормализации.
Этот файл теперь реэкспортирует расширенную версию из models.py.
Оставлен для обратной совместимости.
"""

# Реэкспорт из models.py (определение находится там)
from .models import StandardEntity, RegionalSpecific

__all__ = ["StandardEntity", "RegionalSpecific"]
