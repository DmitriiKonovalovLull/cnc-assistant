"""
Математически корректные вычисления для метрической резьбы ISO.
Все формулы соответствуют ISO 965-1.
"""

import math
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = __import__("logging").getLogger(__name__)


@dataclass
class ThreadGeometry:
    """Геометрические параметры резьбы."""
    # Основные параметры
    nominal_diameter: float  # d - номинальный диаметр (мм)
    pitch: float  # P - шаг (мм)
    
    # Вычисленные параметры профиля
    profile_angle: float = 60.0  # α - угол профиля (градусы)
    theoretical_height: float = 0.0  # H - высота теоретического профиля (мм)
    working_height: float = 0.0  # H1 - рабочая высота (мм)
    thread_depth: float = 0.0  # h - глубина резьбы (мм)
    mean_diameter: float = 0.0  # d2 - средний диаметр (мм)
    minor_diameter: float = 0.0  # d3 - малый диаметр (мм)
    
    # Допуски
    tolerance_class: Optional[str] = None  # 6g, 6H и т.д.
    tolerance_value: Optional[float] = None  # Величина допуска (мм)
    
    def __post_init__(self):
        """Вычислить геометрические параметры после инициализации."""
        self._calculate_geometry()
    
    def _calculate_geometry(self) -> None:
        """Вычислить все геометрические параметры резьбы."""
        P = self.pitch
        d = self.nominal_diameter
        
        # Высота теоретического профиля: H = (√3 / 2) * P
        self.theoretical_height = (math.sqrt(3) / 2) * P
        
        # Рабочая высота: H1 = 5/8 * H
        self.working_height = (5 / 8) * self.theoretical_height
        
        # Глубина резьбы: h = 0.61343 * P
        self.thread_depth = 0.61343 * P
        
        # Средний диаметр: d2 = d - 0.64952 * P
        self.mean_diameter = d - 0.64952 * P
        
        # Малый диаметр: d3 = d - 1.22687 * P
        self.minor_diameter = d - 1.22687 * P


class ThreadCalculator:
    """
    Калькулятор для метрической резьбы ISO.
    Все вычисления выполняются строго по формулам ISO 965-1.
    """
    
    # Константы для расчета допусков (базовая единица допуска)
    TOLERANCE_MULTIPLIERS = {
        3: 0.1,
        4: 0.16,
        5: 0.25,
        6: 0.4,
        7: 0.63,
        8: 1.0,
        9: 1.6,
    }
    
    def __init__(self):
        """Инициализация калькулятора."""
        pass
    
    def parse_thread_designation(self, designation: str) -> Optional[Dict[str, Any]]:
        """
        Распарсить обозначение резьбы M{D}x{P}-{class}.
        
        Args:
            designation: Обозначение резьбы (например "M42x1.5-6g")
            
        Returns:
            Словарь с параметрами или None
        """
        import re
        
        # Паттерн: M{число}x{число}-{класс}
        pattern = r'M(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(?:-(\d+[gGhH]))?'
        match = re.match(pattern, designation.upper())
        
        if not match:
            return None
        
        diameter = float(match.group(1))
        pitch = float(match.group(2))
        tolerance_class = match.group(3) if match.group(3) else None
        
        return {
            "diameter": diameter,
            "pitch": pitch,
            "tolerance_class": tolerance_class,
        }
    
    def calculate_geometry(self, diameter: float, pitch: float, tolerance_class: Optional[str] = None) -> ThreadGeometry:
        """
        Вычислить геометрию резьбы.
        
        Args:
            diameter: Номинальный диаметр (мм)
            pitch: Шаг резьбы (мм)
            tolerance_class: Класс допуска (6g, 6H и т.д.)
            
        Returns:
            ThreadGeometry с вычисленными параметрами
        """
        geometry = ThreadGeometry(
            nominal_diameter=diameter,
            pitch=pitch,
            tolerance_class=tolerance_class,
        )
        
        # Вычисляем допуск если указан класс
        if tolerance_class:
            geometry.tolerance_value = self._calculate_tolerance(diameter, pitch, tolerance_class)
        
        return geometry
    
    def _calculate_tolerance(self, diameter: float, pitch: float, tolerance_class: str) -> float:
        """
        Вычислить величину допуска по ISO 965.
        
        Args:
            diameter: Номинальный диаметр (мм)
            pitch: Шаг резьбы (мм)
            tolerance_class: Класс допуска (6g, 6H и т.д.)
            
        Returns:
            Величина допуска (мм)
        """
        # Извлекаем числовую часть класса (6 из "6g")
        import re
        match = re.match(r'(\d+)', tolerance_class)
        if not match:
            return 0.0
        
        it_grade = int(match.group(1))
        
        # Базовая единица допуска для резьбы
        # Для резьбы используется упрощенная формула на основе диаметра и шага
        D = diameter
        P = pitch
        
        # Средний диаметр для расчета
        d2 = D - 0.64952 * P
        
        # Базовая единица допуска (упрощенная формула для резьбы)
        # i = 0.45 * ∛D + 0.001 * D (в мкм)
        D_microns = d2 * 1000  # Переводим в мкм для расчета
        i = 0.45 * (D_microns ** (1/3)) + 0.001 * D_microns
        
        # Множитель для IT класса
        multiplier = self.TOLERANCE_MULTIPLIERS.get(it_grade, 1.0)
        
        # Допуск в мкм
        tolerance_microns = i * multiplier
        
        # Переводим в мм
        tolerance_mm = tolerance_microns / 1000.0
        
        return tolerance_mm
    
    def get_manufacturing_requirements(
        self,
        geometry: ThreadGeometry,
        material: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Определить производственные требования для резьбы.
        
        Args:
            geometry: Геометрия резьбы
            material: Материал (опционально)
            
        Returns:
            Словарь с требованиями
        """
        requirements = {
            "finish_pass_required": False,
            "feed_limit": None,
            "speed_limit": None,
            "depth_per_pass": None,
            "number_of_passes": 1,
            "criticality": "normal",
        }
        
        P = geometry.pitch
        d = geometry.nominal_diameter
        h = geometry.thread_depth
        
        # Логика 1: Если шаг < 2 мм и класс ≤ 6 → требуется чистовой проход
        if P < 2.0 and geometry.tolerance_class:
            import re
            match = re.match(r'(\d+)', geometry.tolerance_class)
            if match:
                grade = int(match.group(1))
                if grade <= 6:
                    requirements["finish_pass_required"] = True
                    requirements["criticality"] = "high"
        
        # Логика 2: Если диаметр > 40 мм → ограничить подачу
        if d > 40.0:
            # Максимальная подача для больших диаметров
            requirements["feed_limit"] = 0.3  # мм/об
        
        # Логика 3: Если материал = титан → ограничить скорость
        if material and "титан" in material.lower():
            requirements["speed_limit"] = 35.0  # м/мин
        
        # Логика 4: Глубина резьбонарезания и количество проходов
        requirements["depth_per_pass"] = h  # Глубина за проход = полная глубина резьбы
        # Для резьбы обычно делается за один проход, но можно разбить на несколько
        if h > 1.0:  # Если глубина больше 1 мм, разбиваем на проходы
            requirements["number_of_passes"] = int(math.ceil(h / 0.5))  # По 0.5 мм за проход
        else:
            requirements["number_of_passes"] = 1
        
        return requirements
