"""
Математические вычисления геометрии метрической резьбы ISO.
Все формулы соответствуют ISO 965-1, ISO 68-1.
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ThreadGeometry:
    """Геометрия метрической резьбы."""
    nominal_diameter: float  # d - номинальный диаметр (мм)
    pitch: float  # P - шаг (мм)
    profile_angle: float = 60.0  # α - угол профиля (градусы)
    
    # Вычисленные параметры
    theoretical_profile_height: Optional[float] = None  # H
    working_height: Optional[float] = None  # H1
    thread_depth: Optional[float] = None  # h
    pitch_diameter: Optional[float] = None  # d2 - средний диаметр
    minor_diameter: Optional[float] = None  # d3 - малый диаметр
    
    def __post_init__(self):
        """Вычислить геометрические параметры после инициализации."""
        self.calculate_geometry()
    
    def calculate_geometry(self) -> None:
        """
        Вычислить все геометрические параметры резьбы по формулам ISO.
        
        Формулы:
        H = (√3 / 2) * P  - высота теоретического профиля
        H1 = 5/8 * H      - рабочая высота
        h = 0.61343 * P   - глубина резьбы
        d2 = d - 0.64952 * P  - средний диаметр
        d3 = d - 1.22687 * P  - малый диаметр
        """
        P = self.pitch
        
        # Высота теоретического профиля
        self.theoretical_profile_height = (math.sqrt(3) / 2) * P
        
        # Рабочая высота
        self.working_height = (5.0 / 8.0) * self.theoretical_profile_height
        
        # Глубина резьбы
        self.thread_depth = 0.61343 * P
        
        # Средний диаметр
        self.pitch_diameter = self.nominal_diameter - 0.64952 * P
        
        # Малый диаметр
        self.minor_diameter = self.nominal_diameter - 1.22687 * P
    
    def get_thread_area(self) -> float:
        """
        Вычислить площадь поперечного сечения резьбы.
        
        Returns:
            Площадь в мм²
        """
        if self.minor_diameter is None:
            self.calculate_geometry()
        return math.pi * (self.minor_diameter ** 2) / 4
    
    def get_thread_volume_per_length(self, length_mm: float) -> float:
        """
        Вычислить объем материала резьбы на единицу длины.
        
        Args:
            length_mm: Длина резьбы в мм
            
        Returns:
            Объем в мм³
        """
        if self.thread_depth is None:
            self.calculate_geometry()
        
        # Приблизительно: объем = площадь кольца * длина
        outer_area = math.pi * (self.nominal_diameter ** 2) / 4
        inner_area = math.pi * (self.minor_diameter ** 2) / 4
        return (outer_area - inner_area) * length_mm


def calculate_thread_geometry(diameter: float, pitch: float, profile_angle: float = 60.0) -> ThreadGeometry:
    """
    Вычислить геометрию метрической резьбы.
    
    Args:
        diameter: Номинальный диаметр (мм)
        pitch: Шаг резьбы (мм)
        profile_angle: Угол профиля (градусы), по умолчанию 60° для метрической
        
    Returns:
        ThreadGeometry с вычисленными параметрами
    """
    return ThreadGeometry(
        nominal_diameter=diameter,
        pitch=pitch,
        profile_angle=profile_angle
    )


def calculate_thread_passes(thread_depth: float, max_pass_depth: float = 0.5) -> int:
    """
    Вычислить количество проходов для нарезки резьбы.
    
    Args:
        thread_depth: Глубина резьбы (мм)
        max_pass_depth: Максимальная глубина за проход (мм)
        
    Returns:
        Количество проходов
    """
    if thread_depth <= 0 or max_pass_depth <= 0:
        return 1
    
    return math.ceil(thread_depth / max_pass_depth)


def get_thread_tolerance_requirements(pitch: float, tolerance_class: str) -> dict:
    """
    Определить требования к точности нарезки резьбы.
    
    Args:
        pitch: Шаг резьбы (мм)
        tolerance_class: Класс допуска (например "6g", "6H")
        
    Returns:
        Словарь с требованиями:
        - requires_finish_pass: требуется ли чистовой проход
        - max_feed: максимальная подача
        - min_passes: минимальное количество проходов
    """
    # Извлекаем числовую часть класса допуска
    class_num = None
    if tolerance_class:
        for char in tolerance_class:
            if char.isdigit():
                class_num = int(char)
                break
    
    requirements = {
        "requires_finish_pass": False,
        "max_feed_mm_rev": None,
        "min_passes": 1,
    }
    
    # Если шаг < 2 мм и класс ≤ 6 → требуется чистовой проход
    if pitch < 2.0 and class_num is not None and class_num <= 6:
        requirements["requires_finish_pass"] = True
        requirements["min_passes"] = 2
    
    # Ограничение подачи для мелких шагов
    if pitch < 1.0:
        requirements["max_feed_mm_rev"] = pitch * 0.5
    elif pitch < 2.0:
        requirements["max_feed_mm_rev"] = pitch * 0.7
    else:
        requirements["max_feed_mm_rev"] = pitch * 0.9
    
    return requirements
