"""
Источники данных для парсинга.
Список сайтов, форумов, PDF, ГОСТов для извлечения знаний.
"""

from typing import List, Dict, Any
from enum import Enum


class SourceType(Enum):
    """Типы источников данных."""
    FORUM = "forum"
    MANUAL = "manual"
    PDF = "pdf"
    GOST = "gost"
    DATASHEET = "datasheet"
    WEBSITE = "website"


class DataSource:
    """Источник данных для парсинга."""
    
    def __init__(
        self,
        name: str,
        url: str,
        source_type: SourceType,
        description: str = "",
        priority: int = 1
    ):
        """
        Инициализация источника.
        
        Args:
            name: Название источника
            url: URL источника
            source_type: Тип источника
            description: Описание
            priority: Приоритет (1 = высокий, 5 = низкий)
        """
        self.name = name
        self.url = url
        self.source_type = source_type
        self.description = description
        self.priority = priority


# Список источников данных
DATA_SOURCES: List[DataSource] = [
    # Форумы
    DataSource(
        name="CNCZone",
        url="https://www.cnczone.com",
        source_type=SourceType.FORUM,
        description="Форум по ЧПУ обработке",
        priority=2
    ),
    
    # Мануалы производителей
    DataSource(
        name="Sandvik Coromant",
        url="https://www.sandvik.coromant.com",
        source_type=SourceType.MANUAL,
        description="Мануалы по резанию от Sandvik",
        priority=1
    ),
    
    DataSource(
        name="Kennametal",
        url="https://www.kennametal.com",
        source_type=SourceType.MANUAL,
        description="Технические данные Kennametal",
        priority=1
    ),
    
    # ГОСТы
    DataSource(
        name="ГОСТ 26645",
        url="",
        source_type=SourceType.GOST,
        description="ГОСТ по режимам резания",
        priority=1
    ),
    
    # Datasheets
    DataSource(
        name="Tool Catalogs",
        url="",
        source_type=SourceType.DATASHEET,
        description="Каталоги инструментов",
        priority=2
    )
]


def get_sources_by_type(source_type: SourceType) -> List[DataSource]:
    """
    Получить источники по типу.
    
    Args:
        source_type: Тип источника
        
    Returns:
        Список источников
    """
    return [s for s in DATA_SOURCES if s.source_type == source_type]


def get_high_priority_sources() -> List[DataSource]:
    """Получить источники с высоким приоритетом."""
    return [s for s in DATA_SOURCES if s.priority <= 2]
