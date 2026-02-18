"""
Расширенные модели для поддержки всех мировых систем стандартов.
StandardSource, StandardCategory, ThreadData, расширенный StandardEntity.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StandardSource(Enum):
    """Источники стандартов — все мировые системы."""
    GOST = "GOST"  # РФ/ЕАЭС
    OST = "OST"  # СССР/отраслевые
    ISO = "ISO"  # Международный
    DIN = "DIN"  # Германия
    GB = "GB"  # Китай (Guobiao)
    JIS = "JIS"  # Япония
    ANSI = "ANSI"  # США
    ASME = "ASME"  # США (машиностроение)
    BS = "BS"  # Британия
    NF = "NF"  # Франция
    UNI = "UNI"  # Италия
    KS = "KS"  # Корея
    IS = "IS"  # Индия
    SIS = "SIS"  # Швеция
    PN = "PN"  # Польша
    CSN = "CSN"  # Чехия

    def __str__(self) -> str:
        return self.value


class StandardCategory(Enum):
    """Категории стандартов."""
    THREAD = "thread"  # Резьбы всех типов: метрическая, дюймовая, трубная
    TOLERANCE = "tolerance"  # Допуски IT, ANSI, JIS
    FIT = "fit"  # Посадки: H7/h6, H7/k6, H7/s6
    SURFACE = "surface"  # Шероховатость Ra, Rz, RMS
    GROOVE = "groove"  # Канавки, проточки
    MATERIAL = "material"  # Материалы: сталь, алюминий, пластик
    HEAT_TREATMENT = "heat_treatment"  # Термообработка
    COATING = "coating"  # Покрытия

    def __str__(self) -> str:
        return self.value


@dataclass
class RegionalSpecific:
    """Региональная специфика стандарта."""
    region: str  # EU, ASIA, US, CIS, GLOBAL
    equivalent_to: List[Dict[str, Any]] = field(default_factory=list)  # Аналоги в других системах
    notes: Optional[str] = None  # Дополнительные примечания


@dataclass
class ThreadData:
    """
    Данные резьбы с поддержкой всех типов.
    """
    thread_type: str  # metric, whitworth, unified, pipe, trapezoidal, acme, buttress
    diameter: float  # Диаметр (в единицах diameter_unit)
    diameter_unit: str = "mm"  # mm или inch
    pitch: Optional[float] = None  # Шаг (мм) для метрической/трапецеидальной
    tpi: Optional[int] = None  # Threads Per Inch для дюймовых резьб
    tolerance_class: Optional[str] = None  # 6g, 6H, 2A, 2B и т.д.
    profile_angle: float = 60.0  # Угол профиля (градусы): 60 для метрической, 55 для Whitworth, 30 для трапецеидальной
    system: str = "metric"  # metric, imperial, pipe
    thread_series: Optional[str] = None  # UNC, UNF, NPT, BSP и т.д.
    nominal_size: Optional[str] = None  # Номинальный размер (например "1/4-20" для дюймовой)

    def get_pitch_mm(self) -> Optional[float]:
        """Получить шаг в мм (конвертирует TPI если нужно)."""
        if self.pitch is not None:
            return self.pitch
        if self.tpi is not None:
            # TPI → мм: 1 дюйм = 25.4 мм, pitch = 25.4 / tpi
            return 25.4 / self.tpi
        return None

    def get_diameter_mm(self) -> float:
        """Получить диаметр в мм."""
        if self.diameter_unit == "inch":
            return self.diameter * 25.4
        return self.diameter


@dataclass
class StandardEntity:
    """
    Расширенная сущность стандарта после нормализации.
    Поддержка всех мировых систем стандартов.
    """
    id: str
    source: str  # Может быть StandardSource.value или строка
    category: str  # Может быть StandardCategory.value или строка
    normalized_data: Dict[str, Any]
    raw_designation: Optional[str] = None  # Исходное обозначение (например M42x1.5-6g)
    metadata: Dict[str, Any] = field(default_factory=dict)
    regional_specific: Optional[RegionalSpecific] = None  # Региональная специфика

    def get_source_enum(self) -> Optional[StandardSource]:
        """Получить источник как Enum."""
        try:
            return StandardSource(self.source.upper())
        except (ValueError, AttributeError):
            return None

    def get_category_enum(self) -> Optional[StandardCategory]:
        """Получить категорию как Enum."""
        try:
            return StandardCategory(self.category.lower())
        except (ValueError, AttributeError):
            return None

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение из normalized_data."""
        return self.normalized_data.get(key, default)

    def add_equivalent(self, source: str, designation: str, confidence: float = 1.0, notes: Optional[str] = None) -> None:
        """Добавить аналог в другой системе стандартов."""
        if self.regional_specific is None:
            self.regional_specific = RegionalSpecific(region="GLOBAL")
        self.regional_specific.equivalent_to.append({
            "source": source,
            "designation": designation,
            "confidence": confidence,
            "notes": notes,
        })

    def get_equivalents(self, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить список аналогов (опционально фильтр по источнику)."""
        if self.regional_specific is None:
            return []
        if source is None:
            return self.regional_specific.equivalent_to
        return [eq for eq in self.regional_specific.equivalent_to if eq.get("source", "").upper() == source.upper()]


# Вспомогательные функции для работы с источниками и категориями

def get_region_for_source(source: StandardSource) -> str:
    """Определить регион для источника стандарта."""
    region_map = {
        StandardSource.GOST: "CIS",
        StandardSource.OST: "CIS",
        StandardSource.ISO: "GLOBAL",
        StandardSource.DIN: "EU",
        StandardSource.BS: "EU",
        StandardSource.NF: "EU",
        StandardSource.UNI: "EU",
        StandardSource.SIS: "EU",
        StandardSource.PN: "EU",
        StandardSource.CSN: "EU",
        StandardSource.GB: "ASIA",
        StandardSource.JIS: "ASIA",
        StandardSource.KS: "ASIA",
        StandardSource.IS: "ASIA",
        StandardSource.ANSI: "US",
        StandardSource.ASME: "US",
    }
    return region_map.get(source, "GLOBAL")


def is_compatible_sources(source1: StandardSource, source2: StandardSource) -> bool:
    """Проверить совместимость источников (например, ISO совместим со всеми)."""
    if source1 == StandardSource.ISO or source2 == StandardSource.ISO:
        return True
    if source1 == source2:
        return True
    # ГОСТ и ОСТ совместимы
    if {source1, source2} == {StandardSource.GOST, StandardSource.OST}:
        return True
    return False


def normalize_source_string(source_str: str) -> Optional[StandardSource]:
    """Нормализовать строку источника в Enum."""
    if not source_str:
        return None
    source_upper = source_str.upper().strip()
    try:
        return StandardSource(source_upper)
    except ValueError:
        # Попытка найти по частичному совпадению
        for source in StandardSource:
            if source.value.upper() == source_upper or source_upper in source.value.upper():
                return source
        return None


def normalize_category_string(category_str: str) -> Optional[StandardCategory]:
    """Нормализовать строку категории в Enum."""
    if not category_str:
        return None
    category_lower = category_str.lower().strip()
    try:
        return StandardCategory(category_lower)
    except ValueError:
        # Попытка найти по частичному совпадению
        for category in StandardCategory:
            if category.value.lower() == category_lower or category_lower in category.value.lower():
                return category
        return None
