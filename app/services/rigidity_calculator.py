"""
КАЛЬКУЛЯТОР ЖЕСТКОСТИ И ВИБРАЦИИ.
Учитывает отношение вылета к диаметру (L/D) и влияние на режимы резания.
"""

from typing import Dict, Optional, Tuple, Any, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Тип инструмента по жесткости."""
    HSS = "hss"  # Быстрорежущая сталь
    CARBIDE = "carbide"  # Твердый сплав
    CERMET = "cermet"  # Кермет
    CERAMIC = "ceramic"  # Керамика
    CBN = "cbn"  # Кубический нитрид бора
    DIAMOND = "diamond"  # Алмаз


class MaterialVibrationTendency(Enum):
    """Склонность материала к вибрации."""
    LOW = "low"  # Низкая (алюминий)
    MEDIUM = "medium"  # Средняя (углеродистая сталь)
    HIGH = "high"  # Высокая (нержавейка)
    VERY_HIGH = "very_high"  # Очень высокая (титан)


class RigidityCalculator:
    """Калькулятор жесткости и вибрации инструмента."""
    
    # Коэффициенты жесткости по L/D
    RIGIDITY_COEFFICIENTS = {
        # L/D: (K_v для скорости, K_f для подачи, K_ap для глубины)
        (0, 3): (1.0, 1.0, 1.0),  # ≤3 - Жёсткая система
        (3, 5): (0.9, 0.9, 0.85),  # 4-5 - Умеренный риск
        (5, 8): (0.75, 0.8, 0.7),  # 6-8 - Высокий риск
        (8, float('inf')): (0.6, 0.7, 0.5),  # >8 - Почти гарантированный chatter
    }
    
    # Коэффициенты для типов инструментов
    TOOL_TYPE_COEFFICIENTS = {
        ToolType.HSS: 0.7,  # Низкая жёсткость
        ToolType.CARBIDE: 1.0,  # Базовая жёсткость
        ToolType.CERMET: 1.0,
        ToolType.CERAMIC: 0.9,  # Нельзя допускать вибрацию
        ToolType.CBN: 0.85,  # Требуется жёсткая система
        ToolType.DIAMOND: 0.8,
    }
    
    # Склонность материалов к вибрации
    MATERIAL_VIBRATION = {
        'алюминий': MaterialVibrationTendency.LOW,
        'aluminum': MaterialVibrationTendency.LOW,
        'латунь': MaterialVibrationTendency.LOW,
        'brass': MaterialVibrationTendency.LOW,
        'медь': MaterialVibrationTendency.LOW,
        'copper': MaterialVibrationTendency.LOW,
        'сталь': MaterialVibrationTendency.MEDIUM,
        'steel': MaterialVibrationTendency.MEDIUM,
        'чугун': MaterialVibrationTendency.MEDIUM,
        'cast_iron': MaterialVibrationTendency.MEDIUM,
        'нержавейка': MaterialVibrationTendency.HIGH,
        'stainless': MaterialVibrationTendency.HIGH,
        'stainless_steel': MaterialVibrationTendency.HIGH,
        'титан': MaterialVibrationTendency.VERY_HIGH,
        'titanium': MaterialVibrationTendency.VERY_HIGH,
    }
    
    # Дополнительные коэффициенты для материалов с высокой склонностью к вибрации
    VIBRATION_MATERIAL_COEFFICIENTS = {
        MaterialVibrationTendency.LOW: 1.0,
        MaterialVibrationTendency.MEDIUM: 0.95,
        MaterialVibrationTendency.HIGH: 0.85,
        MaterialVibrationTendency.VERY_HIGH: 0.75,
    }
    
    @classmethod
    def calculate_ld_ratio(cls, tool_overhang_mm: float, tool_diameter_mm: float) -> float:
        """
        Рассчитать отношение вылета к диаметру (L/D).
        
        Args:
            tool_overhang_mm: Вылет инструмента (мм)
            tool_diameter_mm: Диаметр инструмента (мм)
            
        Returns:
            Отношение L/D
        """
        if tool_diameter_mm <= 0:
            return 0.0
        return tool_overhang_mm / tool_diameter_mm
    
    @classmethod
    def get_rigidity_coefficients(cls, ld_ratio: float) -> Tuple[float, float, float]:
        """
        Получить коэффициенты жесткости для скорости, подачи и глубины резания.
        
        Args:
            ld_ratio: Отношение L/D
            
        Returns:
            Кортеж (K_v, K_f, K_ap)
        """
        for (min_ld, max_ld), (k_v, k_f, k_ap) in cls.RIGIDITY_COEFFICIENTS.items():
            if min_ld <= ld_ratio < max_ld:
                return (k_v, k_f, k_ap)
        
        # По умолчанию для очень больших L/D
        return (0.5, 0.6, 0.4)
    
    @classmethod
    def get_rigidity_risk_level(cls, ld_ratio: float) -> str:
        """
        Определить уровень риска вибрации по L/D.
        
        Args:
            ld_ratio: Отношение L/D
            
        Returns:
            Уровень риска: 'low', 'moderate', 'high', 'critical'
        """
        if ld_ratio <= 3:
            return 'low'
        elif ld_ratio <= 5:
            return 'moderate'
        elif ld_ratio <= 8:
            return 'high'
        else:
            return 'critical'
    
    @classmethod
    def get_tool_type_from_material(cls, tool_material: str) -> ToolType:
        """
        Определить тип инструмента по материалу.
        
        Args:
            tool_material: Материал инструмента
            
        Returns:
            Тип инструмента
        """
        tool_lower = tool_material.lower()
        
        if 'hss' in tool_lower or 'быстрорез' in tool_lower or 'быстрорежущ' in tool_lower:
            return ToolType.HSS
        elif 'ceramic' in tool_lower or 'керамик' in tool_lower:
            return ToolType.CERAMIC
        elif 'cbn' in tool_lower:
            return ToolType.CBN
        elif 'diamond' in tool_lower or 'алмаз' in tool_lower:
            return ToolType.DIAMOND
        elif 'cermet' in tool_lower or 'кермет' in tool_lower:
            return ToolType.CERMET
        else:
            # По умолчанию - твердый сплав
            return ToolType.CARBIDE
    
    @classmethod
    def get_tool_coefficient(cls, tool_type: ToolType, ld_ratio: float) -> float:
        """
        Получить коэффициент инструмента с учетом L/D.
        
        Args:
            tool_type: Тип инструмента
            ld_ratio: Отношение L/D
            
        Returns:
            Коэффициент для скорости резания
        """
        base_coeff = cls.TOOL_TYPE_COEFFICIENTS.get(tool_type, 1.0)
        
        # Для керамики и CBN при большом L/D не рекомендуется
        if tool_type in [ToolType.CERAMIC, ToolType.CBN] and ld_ratio > 4:
            return base_coeff * 0.7  # Сильное снижение
        
        return base_coeff
    
    @classmethod
    def get_material_vibration_tendency(cls, material: str) -> MaterialVibrationTendency:
        """
        Получить склонность материала к вибрации.
        
        Args:
            material: Название материала
            
        Returns:
            Склонность к вибрации
        """
        material_lower = material.lower()
        
        # Проверяем точные совпадения
        if material_lower in cls.MATERIAL_VIBRATION:
            return cls.MATERIAL_VIBRATION[material_lower]
        
        # Проверяем частичные совпадения
        for key, tendency in cls.MATERIAL_VIBRATION.items():
            if key in material_lower:
                return tendency
        
        # По умолчанию - средняя склонность
        return MaterialVibrationTendency.MEDIUM
    
    @classmethod
    def calculate_adjusted_modes(
        cls,
        base_vc: float,
        base_feed: float,
        base_ap: float,
        tool_overhang_mm: float,
        tool_diameter_mm: float,
        tool_material: str,
        workpiece_material: str,
        operation: str = "turning"
    ) -> Dict[str, Any]:
        """
        Рассчитать скорректированные режимы резания с учетом жесткости.
        
        Args:
            base_vc: Базовая скорость резания (м/мин)
            base_feed: Базовая подача (мм/об)
            base_ap: Базовая глубина резания (мм)
            tool_overhang_mm: Вылет инструмента (мм)
            tool_diameter_mm: Диаметр инструмента (мм)
            tool_material: Материал инструмента
            workpiece_material: Материал заготовки
            operation: Тип операции ("turning" или "milling")
            
        Returns:
            Словарь с скорректированными режимами и информацией о жесткости
        """
        # Рассчитываем L/D
        ld_ratio = cls.calculate_ld_ratio(tool_overhang_mm, tool_diameter_mm)
        
        # Получаем коэффициенты жесткости
        k_v, k_f, k_ap = cls.get_rigidity_coefficients(ld_ratio)
        
        # Определяем тип инструмента
        tool_type = cls.get_tool_type_from_material(tool_material)
        tool_coeff = cls.get_tool_coefficient(tool_type, ld_ratio)
        
        # Учитываем склонность материала к вибрации
        material_tendency = cls.get_material_vibration_tendency(workpiece_material)
        material_coeff = cls.VIBRATION_MATERIAL_COEFFICIENTS[material_tendency]
        
        # Применяем коэффициенты
        adjusted_vc = base_vc * k_v * tool_coeff * material_coeff
        adjusted_feed = base_feed * k_f
        adjusted_ap = base_ap * k_ap
        
        # Для материалов с высокой склонностью к вибрации дополнительно снижаем глубину
        if material_tendency in [MaterialVibrationTendency.HIGH, MaterialVibrationTendency.VERY_HIGH]:
            adjusted_ap = adjusted_ap * 0.9
        
        # Определяем уровень риска
        risk_level = cls.get_rigidity_risk_level(ld_ratio)
        
        # Формируем предупреждения
        warnings = []
        anti_chatter_suggestions = []
        
        if risk_level == 'critical':
            warnings.append(f"⚠️ КРИТИЧЕСКИЙ РИСК ВИБРАЦИИ: L/D = {ld_ratio:.1f} > 8")
            warnings.append("Рекомендуется уменьшить вылет инструмента или использовать демпфирующий держатель")
            anti_chatter_suggestions.extend([
                "Уменьшить вылет инструмента",
                "Использовать демпфирующий держатель",
                "Изменить обороты ±10-15%",
                "Уменьшить глубину резания на 30-50%"
            ])
        elif risk_level == 'high':
            warnings.append(f"⚠️ ВЫСОКИЙ РИСК ВИБРАЦИИ: L/D = {ld_ratio:.1f} (6-8)")
            warnings.append("Рекомендуется снизить режимы резания")
            anti_chatter_suggestions.extend([
                "Уменьшить вылет инструмента",
                "Изменить обороты ±5-10%",
                "Уменьшить глубину резания"
            ])
        elif risk_level == 'moderate':
            warnings.append(f"ℹ️ Умеренный риск вибрации: L/D = {ld_ratio:.1f} (4-5)")
            anti_chatter_suggestions.append("При появлении вибрации изменить обороты ±5%")
        
        # Специальные предупреждения для керамики и CBN
        if tool_type in [ToolType.CERAMIC, ToolType.CBN] and ld_ratio > 4:
            warnings.append(f"⚠️ {tool_type.value.upper()} не рекомендуется при L/D > 4")
            warnings.append("Требуется жёсткая система без вибрации")
        
        # Для фрезерования - дополнительные рекомендации
        if operation == "milling":
            if ld_ratio > 6:
                warnings.append("Для фрезерования при большом L/D:")
                warnings.append("• Уменьшить радиальное зацепление (ae)")
                warnings.append("• Увеличить подачу на зуб (чтобы уйти из резонанса)")
                anti_chatter_suggestions.append("Использовать фрезу с переменным шагом зуба")
        
        return {
            'vc': adjusted_vc,
            'feed': adjusted_feed,
            'ap': adjusted_ap,
            'ld_ratio': ld_ratio,
            'rigidity_coefficients': {
                'k_v': k_v,
                'k_f': k_f,
                'k_ap': k_ap
            },
            'tool_coefficient': tool_coeff,
            'material_coefficient': material_coeff,
            'risk_level': risk_level,
            'warnings': warnings,
            'anti_chatter_suggestions': anti_chatter_suggestions,
            'tool_type': tool_type.value,
            'material_vibration_tendency': material_tendency.value
        }
    
    @classmethod
    def get_anti_chatter_strategy(cls, ld_ratio: float, operation: str = "turning") -> List[str]:
        """
        Получить стратегию борьбы с вибрацией.
        
        Args:
            ld_ratio: Отношение L/D
            operation: Тип операции
            
        Returns:
            Список рекомендаций
        """
        strategies = []
        
        if ld_ratio > 8:
            strategies.extend([
                "1. КРИТИЧНО: Уменьшить вылет инструмента",
                "2. Использовать демпфирующий держатель",
                "3. Изменить обороты ±10-15%",
                "4. Уменьшить глубину резания на 30-50%",
                "5. Уменьшить радиус при вершине (для точения)"
            ])
        elif ld_ratio > 6:
            strategies.extend([
                "1. Уменьшить вылет инструмента",
                "2. Изменить обороты ±5-10%",
                "3. Уменьшить глубину резания",
                "4. Увеличить подачу (чтобы сломать резонанс)"
            ])
        elif ld_ratio > 4:
            strategies.extend([
                "1. При появлении вибрации изменить обороты ±5%",
                "2. Уменьшить глубину резания на 10-20%"
            ])
        
        if operation == "milling" and ld_ratio > 5:
            strategies.extend([
                "• Уменьшить радиальное зацепление (ae)",
                "• Использовать фрезу с переменным шагом зуба"
            ])
        
        return strategies
