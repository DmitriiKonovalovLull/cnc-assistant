"""
ПРОСТОЙ КАЛЬКУЛЯТОР РЕЖИМОВ РЕЗАНИЯ.
Принимает: обработку, станок, материал.
Рассчитывает: Vc, n, f, ap, мощность.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.core.calculator import (
    PhysicsCalculator,
    MaterialConstants,
    OperationType,
    Geometry,
    MaterialProperties,
    ToolProperties,
    MachineLimits,
    CalculationResult,
)
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


@dataclass
class SimpleCalculatorInput:
    """Входные данные для простого калькулятора."""
    operation: str  # "turning" или "milling"
    material: str  # Название материала
    machine_type: str  # Тип станка
    machine_power_kw: Optional[float] = None  # Мощность станка (кВт)
    machine_max_rpm: Optional[float] = None  # Макс. обороты
    diameter_mm: Optional[float] = None  # Диаметр обработки (мм)
    tool_radius_mm: Optional[float] = None  # Радиус инструмента (мм)
    mode: str = "normal"  # "rough", "normal", "finish"


@dataclass
class SimpleCalculatorResult:
    """Результат расчета простого калькулятора."""
    vc_m_min: float  # Скорость резания (м/мин)
    rpm: float  # Обороты (об/мин)
    feed_mm_rev: float  # Подача (мм/об)
    ap_mm: float  # Глубина резания (мм)
    power_kw: float  # Мощность резания (кВт)
    feed_rate_mm_min: float  # Скорость подачи (мм/мин)
    warnings: list = None  # Предупреждения
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SimpleCalculator:
    """
    Простой калькулятор режимов резания.
    Принимает обработку, станок, материал и рассчитывает режимы.
    """
    
    def __init__(self, knowledge_service: Optional[KnowledgeService] = None):
        """
        Инициализация калькулятора.
        
        Args:
            knowledge_service: Сервис знаний для получения данных о материалах и станках
        """
        self.knowledge_service = knowledge_service
        self.physics_calc = PhysicsCalculator()
    
    def calculate(self, input_data: SimpleCalculatorInput) -> SimpleCalculatorResult:
        """
        Рассчитать режимы резания.
        
        Args:
            input_data: Входные данные
            
        Returns:
            Результат расчета
        """
        warnings = []
        
        # 1. Получаем свойства материала
        material_props = self._get_material_properties(input_data.material)
        
        # 2. Получаем ограничения станка
        machine_limits = self._get_machine_limits(
            input_data.machine_type,
            input_data.machine_power_kw,
            input_data.machine_max_rpm
        )
        
        # 3. Определяем свойства инструмента
        tool_props = self._get_tool_properties(input_data.tool_radius_mm)
        
        # 4. Рассчитываем базовые режимы в зависимости от операции
        if input_data.operation.lower() == "milling":
            result = self._calculate_milling(
                material_props, machine_limits, tool_props, input_data, warnings
            )
        else:  # turning по умолчанию
            result = self._calculate_turning(
                material_props, machine_limits, tool_props, input_data, warnings
            )
        
        return result
    
    def _get_material_properties(self, material_name: str) -> MaterialProperties:
        """Получить свойства материала."""
        kc_factor = MaterialConstants.get_kc_factor(material_name)
        machinability = MaterialConstants.get_machinability_factor(material_name)
        
        return MaterialProperties(
            material_type=material_name,
            kc_factor=kc_factor
        )
    
    def _get_machine_limits(
        self,
        machine_type: str,
        power_kw: Optional[float],
        max_rpm: Optional[float]
    ) -> MachineLimits:
        """Получить ограничения станка."""
        # Пытаемся получить из knowledge_service
        if self.knowledge_service:
            machine_data = self.knowledge_service.machines.get(machine_type.lower())
            if machine_data:
                power_kw = power_kw or machine_data.power_kw or 15.0
                max_rpm = max_rpm or machine_data.max_rpm or 3000.0
            else:
                # Значения по умолчанию в зависимости от типа станка
                if "токарный" in machine_type.lower() or "lathe" in machine_type.lower():
                    power_kw = power_kw or 15.0
                    max_rpm = max_rpm or 3000.0
                elif "фрезерный" in machine_type.lower() or "milling" in machine_type.lower():
                    power_kw = power_kw or 10.0
                    max_rpm = max_rpm or 8000.0
                else:
                    power_kw = power_kw or 15.0
                    max_rpm = max_rpm or 3000.0
        else:
            power_kw = power_kw or 15.0
            max_rpm = max_rpm or 3000.0
        
        return MachineLimits(
            max_power_kw=power_kw,
            max_rpm=max_rpm,
            machine_type=machine_type
        )
    
    def _get_tool_properties(self, tool_radius_mm: Optional[float]) -> ToolProperties:
        """Получить свойства инструмента."""
        radius = tool_radius_mm or 0.8  # По умолчанию 0.8 мм
        
        return ToolProperties(
            material="твердый сплав",  # По умолчанию
            insert_radius_mm=radius,
            tool_overhang_mm=30.0  # Стандартный вылет
        )
    
    def _calculate_turning(
        self,
        material: MaterialProperties,
        machine: MachineLimits,
        tool: ToolProperties,
        input_data: SimpleCalculatorInput,
        warnings: list
    ) -> SimpleCalculatorResult:
        """Рассчитать режимы для точения."""
        # Базовые скорости резания в зависимости от материала
        vc_base = self._get_base_cutting_speed(material.material_type, input_data.mode)
        
        # Диаметр обработки
        diameter = input_data.diameter_mm or 50.0  # По умолчанию 50 мм
        
        # Рассчитываем обороты
        rpm = self.physics_calc.calculate_rpm(vc_base, diameter)
        
        # Ограничиваем максимальными оборотами станка
        if rpm > machine.max_rpm:
            rpm = machine.max_rpm
            vc_base = self.physics_calc.calculate_cutting_speed(rpm, diameter)
            warnings.append(f"Обороты ограничены максимумом станка: {machine.max_rpm} об/мин")
        
        # Рассчитываем подачу
        feed = self._calculate_feed(tool.insert_radius_mm, input_data.mode, material.material_type)
        
        # Рассчитываем глубину резания
        ap = self._calculate_depth_of_cut(tool.insert_radius_mm, input_data.mode, diameter)
        
        # Рассчитываем мощность
        power = self.physics_calc.calculate_power(
            material.kc_factor,
            ap,
            feed,
            vc_base
        )
        
        # Проверяем ограничение по мощности
        max_power = machine.max_power_kw * 0.8  # 80% от максимума
        if power > max_power:
            # Корректируем режимы
            scale = max_power / power
            ap *= scale
            power = max_power
            warnings.append(f"Мощность ограничена: {max_power:.2f} кВт (80% от {machine.max_power_kw} кВт)")
        
        # Скорость подачи
        feed_rate = self.physics_calc.calculate_feed_rate(feed, rpm)
        
        return SimpleCalculatorResult(
            vc_m_min=round(vc_base, 1),
            rpm=round(rpm),
            feed_mm_rev=round(feed, 3),
            ap_mm=round(ap, 2),
            power_kw=round(power, 2),
            feed_rate_mm_min=round(feed_rate, 1),
            warnings=warnings
        )
    
    def _calculate_milling(
        self,
        material: MaterialProperties,
        machine: MachineLimits,
        tool: ToolProperties,
        input_data: SimpleCalculatorInput,
        warnings: list
    ) -> SimpleCalculatorResult:
        """Рассчитать режимы для фрезерования."""
        # Базовые скорости резания
        vc_base = self._get_base_cutting_speed(material.material_type, input_data.mode)
        
        # Диаметр фрезы
        diameter = input_data.diameter_mm or tool.insert_radius_mm * 2 or 20.0
        
        # Рассчитываем обороты
        rpm = self.physics_calc.calculate_rpm(vc_base, diameter)
        
        # Ограничиваем максимальными оборотами
        if rpm > machine.max_rpm:
            rpm = machine.max_rpm
            vc_base = self.physics_calc.calculate_cutting_speed(rpm, diameter)
            warnings.append(f"Обороты ограничены максимумом станка: {machine.max_rpm} об/мин")
        
        # Подача на зуб (для фрезерования)
        fz = self._calculate_feed_per_tooth(tool.insert_radius_mm, input_data.mode, material.material_type)
        
        # Количество зубьев (по умолчанию 4)
        z = 4
        
        # Подача на оборот
        feed = fz * z
        
        # Глубина резания
        ap = self._calculate_depth_of_cut(tool.insert_radius_mm, input_data.mode, diameter)
        
        # Для фрезерования нужна ширина резания (ae)
        ae = diameter * 0.5  # 50% диаметра фрезы
        
        # Мощность для фрезерования (упрощенная формула)
        power = (material.kc_factor * ap * ae * fz * z * vc_base) / 60000.0
        
        # Проверка мощности
        max_power = machine.max_power_kw * 0.8
        if power > max_power:
            scale = max_power / power
            ap *= scale
            power = max_power
            warnings.append(f"Мощность ограничена: {max_power:.2f} кВт")
        
        # Скорость подачи для фрезерования
        feed_rate = fz * z * rpm
        
        return SimpleCalculatorResult(
            vc_m_min=round(vc_base, 1),
            rpm=round(rpm),
            feed_mm_rev=round(feed, 3),
            ap_mm=round(ap, 2),
            power_kw=round(power, 2),
            feed_rate_mm_min=round(feed_rate, 1),
            warnings=warnings
        )
    
    def _get_base_cutting_speed(self, material_type: str, mode: str) -> float:
        """Получить базовую скорость резания для материала."""
        material_lower = material_type.lower()
        
        # Базовые скорости для разных материалов (м/мин)
        speed_map = {
            "сталь": 150.0,
            "steel": 150.0,
            "алюминий": 300.0,
            "aluminum": 300.0,
            "титан": 80.0,
            "titanium": 80.0,
            "чугун": 120.0,
            "cast_iron": 120.0,
            "нержавеющая": 100.0,
            "stainless": 100.0,
        }
        
        # Ищем материал
        vc = 150.0  # По умолчанию
        for key, value in speed_map.items():
            if key in material_lower:
                vc = value
                break
        
        # Корректируем по режиму
        if mode.lower() == "rough":
            vc *= 0.9  # Черновая - немного ниже
        elif mode.lower() == "finish":
            vc *= 1.2  # Чистовая - выше
        
        return vc
    
    def _calculate_feed(self, radius_mm: float, mode: str, material_type: str) -> float:
        """Рассчитать подачу для точения."""
        # Базовая подача как доля радиуса
        base_feed = radius_mm * 0.6
        
        # Корректировка по режиму
        if mode.lower() == "rough":
            feed = base_feed * 1.0
        elif mode.lower() == "finish":
            feed = base_feed * 0.5
        else:  # normal
            feed = base_feed * 0.7
        
        # Корректировка по материалу
        material_lower = material_type.lower()
        if "алюминий" in material_lower or "aluminum" in material_lower:
            feed *= 1.5
        elif "титан" in material_lower or "titanium" in material_lower:
            feed *= 0.7
        
        return max(0.05, feed)  # Минимум 0.05 мм/об
    
    def _calculate_feed_per_tooth(self, radius_mm: float, mode: str, material_type: str) -> float:
        """Рассчитать подачу на зуб для фрезерования."""
        # Базовая подача на зуб
        base_fz = radius_mm * 0.1
        
        # Корректировка по режиму
        if mode.lower() == "rough":
            fz = base_fz * 1.2
        elif mode.lower() == "finish":
            fz = base_fz * 0.5
        else:  # normal
            fz = base_fz * 0.8
        
        # Корректировка по материалу
        material_lower = material_type.lower()
        if "алюминий" in material_lower or "aluminum" in material_lower:
            fz *= 1.5
        elif "титан" in material_lower or "titanium" in material_lower:
            fz *= 0.6
        
        return max(0.05, fz)  # Минимум 0.05 мм/зуб
    
    def _calculate_depth_of_cut(self, radius_mm: float, mode: str, diameter_mm: float) -> float:
        """Рассчитать глубину резания."""
        # Максимальная глубина по радиусу пластины
        max_ap_by_radius = radius_mm * 0.67  # 2/3 радиуса
        
        # Корректировка по режиму
        if mode.lower() == "rough":
            ap = max_ap_by_radius * 1.0
        elif mode.lower() == "finish":
            ap = max_ap_by_radius * 0.3
        else:  # normal
            ap = max_ap_by_radius * 0.7
        
        # Ограничение по диаметру (не более 10% диаметра для безопасности)
        max_ap_by_diameter = diameter_mm * 0.1
        ap = min(ap, max_ap_by_diameter)
        
        return max(0.5, ap)  # Минимум 0.5 мм
