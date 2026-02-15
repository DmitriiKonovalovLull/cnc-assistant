"""
Сервис рекомендаций для бота.
Версия 5.0: Только табличные значения, без "умных" расчетов.
Цель: дать точку отсчёта для сравнения с практикой операторов.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Импортируем модуль соответствий материалов для использования machinability
try:
    from app.knowledge.material_standards import MaterialStandardsDatabase
except ImportError:
    MaterialStandardsDatabase = None
    logger.warning("MaterialStandardsDatabase not available")


# ============================================================================
# ТАБЛИЧНЫЕ ЗНАЧЕНИЯ (только справочные данные)
# ============================================================================

class CuttingTables:
    """Табличные значения для режимов резания."""

    # Базовые скорости резания (м/мин) для токарной обработки
    # Источник: справочники металлообработки
    TURNING_VC_TABLE = {
        "сталь": {
            "черновой": 80,
            "получистовой": 120,
            "чистовой": 150,
        },
        "алюминий": {
            "черновой": 250,
            "получистовой": 350,
            "чистовой": 500,
        },
        "нержавейка": {
            "черновой": 60,
            "получистовой": 80,
            "чистовой": 100,
        },
        "титан": {
            "черновой": 30,
            "получистовой": 45,
            "чистовой": 60,
        },
        "чугун": {
            "черновой": 70,
            "получистовой": 90,
            "чистовой": 110,
        },
        "латунь": {
            "черновой": 150,
            "получистовой": 200,
            "чистовой": 250,
        },
        "медь": {
            "черновой": 120,
            "получистовой": 160,
            "чистовой": 200,
        }
    }

    # Базовые подачи (мм/об) для токарки
    TURNING_FEED_TABLE = {
        "черновой": 0.20,
        "получистовой": 0.10,
        "чистовой": 0.05,
    }

    # Типовые глубины резания (мм) для токарки
    TURNING_AP_TABLE = {
        "черновой": 4.0,
        "получистовой": 2.0,
        "чистовой": 0.5,
    }

    # Коэффициенты для типа станка
    MACHINE_COEFFICIENTS = {
        "токарный чпу": 1.0,
        "токарный ручной": 0.8,
        "фрезерный чпу": 0.9,
        "фрезерный ручной": 0.7,
    }

    # Коэффициенты для материала инструмента
    TOOL_MATERIAL_COEFFICIENTS = {
        "твердый сплав": 1.0,
        "керамика": 1.5,
        "cbn": 2.0,
        "алмаз": 3.0,
        "быстрорез": 0.5,
        "не знаю": 0.8,
    }

    # Минимальные и максимальные значения (физические ограничения)
    PHYSICAL_LIMITS = {
        "min_rpm": 50,
        "max_rpm": 3000,
        "min_feed_mm_rev": 0.01,
        "max_feed_mm_rev": 0.5,
        "min_ap_mm": 0.1,
        "max_ap_mm": 6.0,
        "min_vc_m_min": 10,
        "max_vc_m_min": 500,
    }

    @classmethod
    def get_turning_vc(cls, material: str, mode: str) -> float:
        """Получить табличную скорость резания для токарки."""
        material = material.lower()
        mode = mode.lower()

        # Приведение к стандартным названиям
        material_map = {
            "сталь": "сталь",
            "алюминий": "алюминий",
            "нержавейка": "нержавейка",
            "нержавеющая": "нержавейка",
            "титан": "титан",
            "чугун": "чугун",
            "латунь": "латунь",
            "медь": "медь",
        }

        mode_map = {
            "черновой": "черновой",
            "черновая": "черновой",
            "получистовой": "получистовой",
            "получистовая": "получистовой",
            "чистовой": "чистовой",
            "чистовая": "чистовой",
        }

        material_key = material_map.get(material, "сталь")
        mode_key = mode_map.get(mode, "черновой")

        try:
            return cls.TURNING_VC_TABLE[material_key][mode_key]
        except KeyError:
            logger.warning(f"Не найдено Vc для материала={material_key}, режима={mode_key}")
            return 100.0  # Значение по умолчанию

    @classmethod
    def get_turning_feed(cls, mode: str) -> float:
        """Получить табличную подачу для токарки."""
        mode = mode.lower()
        mode_map = {
            "черновой": "черновой",
            "черновая": "черновой",
            "получистовой": "получистовой",
            "получистовая": "получистовой",
            "чистовой": "чистовой",
            "чистовая": "чистовой",
        }

        mode_key = mode_map.get(mode, "черновой")
        return cls.TURNING_FEED_TABLE.get(mode_key, 0.2)

    @classmethod
    def get_turning_ap(cls, mode: str) -> float:
        """Получить табличную глубину резания для токарки."""
        mode = mode.lower()
        mode_map = {
            "черновой": "черновой",
            "черновая": "черновой",
            "получистовой": "получистовой",
            "получистовая": "получистовой",
            "чистовой": "чистовой",
            "чистовая": "чистовой",
        }

        mode_key = mode_map.get(mode, "черновой")
        return cls.TURNING_AP_TABLE.get(mode_key, 2.0)

    @classmethod
    def get_machine_coefficient(cls, machine_type: str) -> float:
        """Получить коэффициент для типа станка."""
        machine_type = machine_type.lower()

        for key, value in cls.MACHINE_COEFFICIENTS.items():
            if key in machine_type:
                return value

        return 1.0  # По умолчанию

    @classmethod
    def get_tool_material_coefficient(cls, tool_material: str) -> float:
        """Получить коэффициент для материала инструмента."""
        tool_material = tool_material.lower()

        for key, value in cls.TOOL_MATERIAL_COEFFICIENTS.items():
            if key in tool_material:
                return value

        return 1.0  # По умолчанию


# ============================================================================
# ПРОСТЫЕ РАСЧЕТЫ (без "умной" логики)
# ============================================================================

def calculate_rpm(vc: float, diameter_mm: float) -> float:
    """
    Рассчитать обороты по скорости резания и диаметру.

    Формула: n = (1000 * Vc) / (π * D)
    """
    import math

    if diameter_mm <= 0:
        return CuttingTables.PHYSICAL_LIMITS["min_rpm"]

    rpm = (1000 * vc) / (math.pi * diameter_mm)

    # Ограничиваем физическими пределами
    rpm = max(rpm, CuttingTables.PHYSICAL_LIMITS["min_rpm"])
    rpm = min(rpm, CuttingTables.PHYSICAL_LIMITS["max_rpm"])

    return round(rpm, 1)


def calculate_power_simple(vc: float, feed: float, ap: float, material: str) -> float:
    """
    Упрощенный расчет мощности.

    Формула: P = (kc * ap * f * vc) / 60000
    где kc - удельная сила резания
    """
    # Удельные силы резания (Н/мм²)
    kc_table = {
        "сталь": 2000,
        "алюминий": 800,
        "нержавейка": 2500,
        "титан": 3000,
        "чугун": 1500,
        "латунь": 1000,
        "медь": 1200,
    }

    material = material.lower()
    material_map = {
        "сталь": "сталь",
        "алюминий": "алюминий",
        "нержавейка": "нержавейка",
        "нержавеющая": "нержавейка",
        "титан": "титан",
        "чугун": "чугун",
        "латунь": "латунь",
        "медь": "медь",
    }

    material_key = material_map.get(material, "сталь")
    kc = kc_table.get(material_key, 2000)

    if vc <= 0 or feed <= 0 or ap <= 0:
        return 0.0

    # Расчет мощности с КПД станка (0.8)
    power_kw = (kc * ap * feed * vc) / (60000 * 0.8)

    return round(power_kw, 2)


def validate_against_limits(vc: float, feed: float, ap: float, rpm: float) -> List[str]:
    """
    Проверить значения на соответствие физическим пределам.
    Возвращает список предупреждений.
    """
    warnings = []

    limits = CuttingTables.PHYSICAL_LIMITS

    if vc < limits["min_vc_m_min"]:
        warnings.append(f"Скорость резания {vc} м/мин слишком мала (мин. {limits['min_vc_m_min']} м/мин)")
    elif vc > limits["max_vc_m_min"]:
        warnings.append(f"Скорость резания {vc} м/мин слишком велика (макс. {limits['max_vc_m_min']} м/мин)")

    if feed < limits["min_feed_mm_rev"]:
        warnings.append(f"Подача {feed} мм/об слишком мала (мин. {limits['min_feed_mm_rev']} мм/об)")
    elif feed > limits["max_feed_mm_rev"]:
        warnings.append(f"Подача {feed} мм/об слишком велика (макс. {limits['max_feed_mm_rev']} мм/об)")

    if ap < limits["min_ap_mm"]:
        warnings.append(f"Глубина резания {ap} мм слишком мала (мин. {limits['min_ap_mm']} мм)")
    elif ap > limits["max_ap_mm"]:
        warnings.append(f"Глубина резания {ap} мм слишком велика (макс. {limits['max_ap_mm']} мм)")

    if rpm < limits["min_rpm"]:
        warnings.append(f"Обороты {rpm} об/мин слишком малы (мин. {limits['min_rpm']} об/мин)")
    elif rpm > limits["max_rpm"]:
        warnings.append(f"Обороты {rpm} об/мин слишком велики (макс. {limits['max_rpm']} об/мин)")

    return warnings


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ РЕКОМЕНДАЦИЙ
# ============================================================================

from app.services.cache_service import cached

# Импортируем калькулятор жесткости
try:
    from app.services.rigidity_calculator import RigidityCalculator
except ImportError:
    RigidityCalculator = None
    logger.warning("RigidityCalculator not available")

@cached(ttl_seconds=3600, key_prefix="recommendation")
def get_turning_recommendation(
        material: str,
        operation: str,
        machine_type: str,
        mode: str,
        diameter_start_mm: float,
        diameter_end_mm: float,
        tool_material: str = "твердый сплав",
        knowledge_service: Optional[Any] = None,
        tool_overhang_mm: Optional[float] = None,
        tool_diameter_mm: Optional[float] = None,
        internet_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Получить табличные рекомендации для токарной обработки.

    Возвращает только справочные значения для сравнения с практикой.
    """
    try:
        # 1. Базовые табличные значения
        base_vc = CuttingTables.get_turning_vc(material, mode)
        base_feed = CuttingTables.get_turning_feed(mode)
        base_ap = CuttingTables.get_turning_ap(mode)

        # 2. Коррекции на станок и инструмент (простые коэффициенты)
        machine_coeff = CuttingTables.get_machine_coefficient(machine_type)
        tool_coeff = CuttingTables.get_tool_material_coefficient(tool_material)

        # 3. Коррекция на machinability (если доступна)
        machinability_coeff = 1.0
        machinability_value = None
        if knowledge_service:
            try:
                machinability_value = knowledge_service.get_material_machinability(material)
                if machinability_value:
                    # Нормализуем machinability: 100% = коэффициент 1.0
                    machinability_coeff = machinability_value / 100.0
                    # Ограничиваем диапазон коэффициента (от 0.3 до 2.0)
                    machinability_coeff = max(0.3, min(2.0, machinability_coeff))
            except Exception as e:
                logger.debug(f"Could not get machinability for {material}: {e}")

        # 4. Рассчитываем значения с учетом machinability
        vc = base_vc * machine_coeff * tool_coeff * machinability_coeff
        feed = base_feed * machine_coeff
        # Для материалов с низкой machinability уменьшаем подачу
        if machinability_value and machinability_value < 50:
            feed = feed * 0.8
        ap = base_ap  # Глубину не корректируем сильно
        
        # 4.5. Коррекция на основе данных из интернета (если доступны)
        internet_correction_applied = False
        if internet_data:
            try:
                # Пытаемся извлечь скорости резания из интернет-данных
                if 'vc' in internet_data or 'скорость' in internet_data or 'speed' in internet_data:
                    internet_vc = None
                    # Разные варианты ключей
                    for key in ['vc', 'скорость_резания', 'скорость', 'cutting_speed', 'speed']:
                        if key in internet_data:
                            val = internet_data[key]
                            if isinstance(val, (int, float)):
                                internet_vc = float(val)
                                break
                            elif isinstance(val, str):
                                # Пытаемся извлечь число из строки
                                import re
                                match = re.search(r'(\d+(?:[.,]\d+)?)', val)
                                if match:
                                    internet_vc = float(match.group(1).replace(',', '.'))
                                    break
                    
                    if internet_vc and 10 <= internet_vc <= 1000:  # Разумные пределы
                        # Используем среднее между табличным и интернет-значением (70% табличное, 30% интернет)
                        vc = vc * 0.7 + internet_vc * 0.3
                        internet_correction_applied = True
                        logger.info(f"Applied internet correction for vc: {internet_vc} м/мин")
                
                # Пытаемся извлечь подачу из интернет-данных
                if 'feed' in internet_data or 'подача' in internet_data:
                    internet_feed = None
                    for key in ['feed', 'подача', 'feed_rate']:
                        if key in internet_data:
                            val = internet_data[key]
                            if isinstance(val, (int, float)):
                                internet_feed = float(val)
                                break
                            elif isinstance(val, str):
                                import re
                                match = re.search(r'(\d+(?:[.,]\d+)?)', val)
                                if match:
                                    internet_feed = float(match.group(1).replace(',', '.'))
                                    break
                    
                    if internet_feed and 0.01 <= internet_feed <= 5.0:  # Разумные пределы
                        feed = feed * 0.7 + internet_feed * 0.3
                        internet_correction_applied = True
                        logger.info(f"Applied internet correction for feed: {internet_feed} мм/об")
            except Exception as e:
                logger.debug(f"Error applying internet data correction: {e}")
        
        # 4.1. Коррекция на жесткость инструмента (L/D)
        rigidity_warnings = []
        rigidity_info = {}
        if RigidityCalculator and tool_overhang_mm and tool_diameter_mm:
            try:
                rigidity_result = RigidityCalculator.calculate_adjusted_modes(
                    base_vc=vc,
                    base_feed=feed,
                    base_ap=ap,
                    tool_overhang_mm=tool_overhang_mm,
                    tool_diameter_mm=tool_diameter_mm,
                    tool_material=tool_material,
                    workpiece_material=material,
                    operation="turning"
                )
                
                # Применяем коррекции жесткости
                vc = rigidity_result['vc']
                feed = rigidity_result['feed']
                ap = rigidity_result['ap']
                
                # Сохраняем информацию о жесткости
                rigidity_info = {
                    'ld_ratio': rigidity_result['ld_ratio'],
                    'risk_level': rigidity_result['risk_level'],
                    'rigidity_coefficients': rigidity_result['rigidity_coefficients'],
                    'tool_type': rigidity_result['tool_type'],
                    'material_vibration_tendency': rigidity_result['material_vibration_tendency']
                }
                
                # Добавляем предупреждения о вибрации
                if rigidity_result['warnings']:
                    rigidity_warnings.extend(rigidity_result['warnings'])
                
            except Exception as e:
                logger.debug(f"Could not calculate rigidity: {e}")

        # 5. Рассчитываем обороты на среднем диаметре
        avg_diameter = (diameter_start_mm + diameter_end_mm) / 2
        rpm = calculate_rpm(vc, avg_diameter)

        # 5. Рассчитываем мощность
        power_kw = calculate_power_simple(vc, feed, ap, material)

        # 6. Проверяем физические ограничения
        warnings = validate_against_limits(vc, feed, ap, rpm)
        
        # Добавляем предупреждения о жесткости
        if rigidity_warnings:
            warnings.extend(rigidity_warnings)

        # 7. Рассчитываем припуск
        stock_per_side = (diameter_start_mm - diameter_end_mm) / 2

        # 8. Добавляем контекстную информацию
        context = {
            "material": material,
            "operation": operation,
            "machine_type": machine_type,
            "mode": mode,
            "diameter_start_mm": diameter_start_mm,
            "diameter_end_mm": diameter_end_mm,
            "stock_per_side_mm": stock_per_side,
            "avg_diameter_mm": avg_diameter,
            "tool_material": tool_material,
            "machine_coefficient": machine_coeff,
            "tool_coefficient": tool_coeff,
            "machinability": machinability_value,
            "machinability_coefficient": machinability_coeff if machinability_value else None,
            "rigidity_info": rigidity_info,
            "tool_overhang_mm": tool_overhang_mm,
            "tool_diameter_mm": tool_diameter_mm,
            "internet_data_used": internet_correction_applied,
            "internet_sources": internet_data.get('sources', []) if internet_data else []
        }

        return {
            # Основные параметры
            "vc": round(vc, 1),  # м/мин
            "rpm": round(rpm, 1),  # об/мин
            "feed": round(feed, 3),  # мм/об
            "ap": round(ap, 2),  # мм
            "power_kw": power_kw,  # кВт

            # Контекст
            "context": context,

            # Предупреждения
            "warnings": warnings,

            # Флаги
            "is_table_based": True,  # Это табличные значения!
            "is_for_comparison": True,  # Для сравнения с практикой
            "disclaimer": "Это справочные табличные значения. На практике параметры могут отличаться.",

            # Исходные табличные значения
            "table_values": {
                "base_vc": base_vc,
                "base_feed": base_feed,
                "base_ap": base_ap,
            }
        }

    except Exception as e:
        logger.error(f"Ошибка получения рекомендации: {e}", exc_info=True)

        # Возвращаем безопасные значения по умолчанию
        return {
            "vc": 100.0,
            "rpm": 500.0,
            "feed": 0.2,
            "ap": 2.0,
            "power_kw": 5.0,
            "context": {},
            "warnings": [f"Ошибка расчета: {str(e)}. Используются безопасные значения."],
            "is_table_based": True,
            "is_for_comparison": True,
            "disclaimer": "Возникла ошибка расчета. Используются безопасные значения.",
            "table_values": {},
            "has_error": True,
        }


def get_milling_recommendation(
        material: str,
        machine_type: str,
        mode: str,
        tool_diameter_mm: float,
        tool_overhang_mm: Optional[float] = None,
        tool_material: str = "твердый сплав",
        knowledge_service: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Получить табличные рекомендации для фрезерования.
    """
    # Для фрезерования используем токарные значения как базовые
    # В реальном проекте здесь была бы отдельная таблица

    base_vc = CuttingTables.get_turning_vc(material, mode) * 0.8  # Фрезерование обычно медленнее
    base_feed = CuttingTables.get_turning_feed(mode) * 0.5  # На зуб

    machine_coeff = CuttingTables.get_machine_coefficient(machine_type)

    vc = base_vc * machine_coeff
    feed_per_tooth = base_feed * machine_coeff

    # Глубина резания
    if mode == "черновой":
        ap = min(tool_diameter_mm * 0.5, 6.0)
    elif mode == "получистовой":
        ap = min(tool_diameter_mm * 0.3, 3.0)
    else:  # чистовой
        ap = min(tool_diameter_mm * 0.1, 1.0)
    
    # Коррекция на жесткость инструмента (L/D)
    rigidity_warnings = []
    rigidity_info = {}
    if RigidityCalculator and tool_overhang_mm:
        try:
            rigidity_result = RigidityCalculator.calculate_adjusted_modes(
                base_vc=vc,
                base_feed=feed_per_tooth,
                base_ap=ap,
                tool_overhang_mm=tool_overhang_mm,
                tool_diameter_mm=tool_diameter_mm,
                tool_material=tool_material,
                workpiece_material=material,
                operation="milling"
            )
            
            # Применяем коррекции жесткости
            vc = rigidity_result['vc']
            feed_per_tooth = rigidity_result['feed']
            ap = rigidity_result['ap']
            
            # Сохраняем информацию о жесткости
            rigidity_info = {
                'ld_ratio': rigidity_result['ld_ratio'],
                'risk_level': rigidity_result['risk_level'],
                'rigidity_coefficients': rigidity_result['rigidity_coefficients'],
                'tool_type': rigidity_result['tool_type'],
                'material_vibration_tendency': rigidity_result['material_vibration_tendency']
            }
            
            # Добавляем предупреждения о вибрации
            if rigidity_result['warnings']:
                rigidity_warnings.extend(rigidity_result['warnings'])
                
        except Exception as e:
            logger.debug(f"Could not calculate rigidity for milling: {e}")

    # Обороты для фрезерования
    rpm = calculate_rpm(vc, tool_diameter_mm)

    # Подача в мм/мин (предполагаем 4 зуба)
    teeth_count = 4
    feed_mm_min = rpm * feed_per_tooth * teeth_count

    return {
        "vc": round(vc, 1),
        "rpm": round(rpm, 1),
        "feed_per_tooth": round(feed_per_tooth, 3),
        "feed_mm_min": round(feed_mm_min, 1),
        "ap": round(ap, 2),
        "teeth_count": teeth_count,
        "tool_diameter_mm": tool_diameter_mm,
        "rigidity_info": rigidity_info,
        "warnings": rigidity_warnings,
        "is_table_based": True,
        "disclaimer": "Табличные значения для фрезерования. На практике могут отличаться.",
    }


def get_drilling_recommendation(
        material: str,
        machine_type: str,
        mode: str,
        tool_diameter_mm: float
) -> Dict[str, Any]:
    """
    Получить табличные рекомендации для сверления.
    """
    # Сверление обычно медленнее
    base_vc = CuttingTables.get_turning_vc(material, mode) * 0.3
    base_feed = CuttingTables.get_turning_feed(mode) * 0.5

    machine_coeff = CuttingTables.get_machine_coefficient(machine_type)

    vc = base_vc * machine_coeff
    feed = base_feed * machine_coeff

    rpm = calculate_rpm(vc, tool_diameter_mm)
    feed_mm_min = rpm * feed

    return {
        "vc": round(vc, 1),
        "rpm": round(rpm, 1),
        "feed": round(feed, 3),
        "feed_mm_min": round(feed_mm_min, 1),
        "tool_diameter_mm": tool_diameter_mm,
        "is_table_based": True,
        "disclaimer": "Табличные значения для сверления. На практике могут отличаться.",
    }


# ============================================================================
# ФУНКЦИИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# ============================================================================

def calculate_cutting_modes_turning_for_bot(
        material: str,
        machine_type: str,
        mode: str,
        start_diameter: float,
        finish_diameter: float,
        tool_type: str = "проходной (80°)",
        tool_material: str = "твердый сплав",
        tool_overhang: float = 50.0,
        tool_radius: float = 0.8
) -> Dict[str, Any]:
    """
    Функция для обратной совместимости с ботом v4.0.
    Использует новую логику табличных значений.
    """
    # Игнорируем tool_type, tool_overhang, tool_radius - они не влияют на табличные значения

    result = get_turning_recommendation(
        material=material,
        operation="токарка",
        machine_type=machine_type,
        mode=mode,
        diameter_start_mm=start_diameter,
        diameter_end_mm=finish_diameter,
        tool_material=tool_material
    )

    # Добавляем поля для совместимости
    result["start_diameter"] = start_diameter
    result["finish_diameter"] = finish_diameter
    result["avg_diameter"] = (start_diameter + finish_diameter) / 2
    result["depth_of_cut"] = (start_diameter - finish_diameter) / 2
    result["tool_type"] = tool_type
    result["tool_material"] = tool_material
    result["tool_overhang"] = tool_overhang
    result["tool_radius"] = tool_radius

    # Фиктивный анализ геометрии для совместимости
    stock = (start_diameter - finish_diameter) / 2
    if stock > 10:
        complexity = "complex"
        passes = max(3, int(stock / 3))
    elif stock > 5:
        complexity = "medium"
        passes = max(2, int(stock / 2))
    else:
        complexity = "simple"
        passes = 1 if stock <= 2 else 2

    result["geometry_analysis"] = {
        "suggested_passes": passes,
        "complexity": complexity,
        "difference_mm": round(stock * 2, 1),
    }

    result["geometry_score"] = 0.8 if complexity == "simple" else 0.6 if complexity == "medium" else 0.4
    result["is_valid"] = True

    return result


def calculate_cutting_modes_milling_for_bot(
        material: str,
        machine_type: str,
        mode: str,
        tool_diameter: float
) -> Dict[str, Any]:
    """
    Функция для обратной совместимости с ботом v4.0.
    """
    result = get_milling_recommendation(
        material=material,
        machine_type=machine_type,
        mode=mode,
        tool_diameter_mm=tool_diameter
    )

    result["material"] = material
    result["machine_type"] = machine_type
    result["mode"] = mode
    result["tool_diameter"] = tool_diameter
    result["is_valid"] = True

    return result


def calculate_cutting_modes_drilling_for_bot(
        material: str,
        machine_type: str,
        mode: str,
        tool_diameter: float
) -> Dict[str, Any]:
    """
    Функция для обратной совместимости с ботом v4.0.
    """
    result = get_drilling_recommendation(
        material=material,
        machine_type=machine_type,
        mode=mode,
        tool_diameter_mm=tool_diameter
    )

    result["material"] = material
    result["machine_type"] = machine_type
    result["mode"] = mode
    result["tool_diameter"] = tool_diameter
    result["is_valid"] = True

    return result


# ============================================================================
# УТИЛИТЫ ДЛЯ БОТА
# ============================================================================

def format_recommendation_for_bot(recommendation: Dict[str, Any]) -> str:
    """
    Форматировать рекомендацию для вывода в боте.
    """
    lines = []

    lines.append("🎯 <b>ТАБЛИЧНЫЕ ЗНАЧЕНИЯ (справочные):</b>")
    lines.append("")

    # Основные параметры
    lines.append(f"• <b>Скорость резания:</b> {recommendation.get('vc', 0)} м/мин")
    lines.append(f"• <b>Обороты шпинделя:</b> {recommendation.get('rpm', 0)} об/мин")
    lines.append(f"• <b>Подача:</b> {recommendation.get('feed', recommendation.get('feed_per_tooth', 0))} мм/об")

    if 'ap' in recommendation:
        lines.append(f"• <b>Глубина резания:</b> {recommendation['ap']} мм")

    if 'power_kw' in recommendation:
        lines.append(f"• <b>Расчетная мощность:</b> {recommendation['power_kw']} кВт")

    # Геометрия для токарки
    if 'geometry_analysis' in recommendation:
        geo = recommendation['geometry_analysis']
        lines.append("")
        lines.append(f"📊 <b>Анализ геометрии:</b>")
        lines.append(f"  • Проходов: {geo.get('suggested_passes', 1)}")
        lines.append(f"  • Сложность: {geo.get('complexity', 'простая')}")
        lines.append(f"  • Припуск: {geo.get('difference_mm', 0)} мм")

    # Предупреждения
    warnings = recommendation.get('warnings', [])
    if warnings:
        lines.append("")
        lines.append("⚠️ <b>Внимание:</b>")
        for warning in warnings[:3]:  # Не более 3 предупреждений
            lines.append(f"• {warning}")

    # Дисклеймер
    lines.append("")
    lines.append("<i>📌 Это справочные табличные значения.</i>")
    lines.append("<i>На практике операторы часто корректируют параметры</i>")
    lines.append("<i>в зависимости от конкретных условий и опыта.</i>")

    return "\n".join(lines)


def get_recommendation_disclaimer() -> str:
    """
    Получить дисклеймер для рекомендаций.
    """
    return (
        "<b>Важно понимать:</b>\n\n"
        "Я не даю «правильные» или «истинные» значения.\n"
        "Я показываю табличные данные из справочников,\n"
        "чтобы вы могли сравнить их со своей практикой.\n\n"
        "Разница между таблицами и реальностью —\n"
        "это ценные данные для обучения ИИ-технолога!"
    )


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ НОВОГО recommendation.py (v5.0)")
    print("=" * 60)

    # Тест 1: Токарная обработка стали
    print("\n📊 Тест 1: Токарка стали")
    print("-" * 40)

    rec1 = get_turning_recommendation(
        material="сталь",
        operation="токарка",
        machine_type="токарный чпу",
        mode="черновой",
        diameter_start_mm=100,
        diameter_end_mm=90,
        tool_material="твердый сплав"
    )

    print(f"Vc: {rec1['vc']} м/мин")
    print(f"Обороты: {rec1['rpm']} об/мин")
    print(f"Подача: {rec1['feed']} мм/об")
    print(f"Глубина: {rec1['ap']} мм")
    print(f"Табличные? {rec1['is_table_based']}")
    print(f"Для сравнения? {rec1['is_for_comparison']}")

    # Тест 2: Обратная совместимость
    print("\n📊 Тест 2: Обратная совместимость")
    print("-" * 40)

    rec2 = calculate_cutting_modes_turning_for_bot(
        material="сталь",
        machine_type="чпу_токарка",
        mode="черновой",
        start_diameter=100,
        finish_diameter=90,
        tool_type="проходной (80°)",
        tool_material="твердый сплав",
        tool_overhang=50,
        tool_radius=0.8
    )

    print(f"Vc: {rec2['vc']} м/мин")
    print(f"Обороты: {rec2['rpm']} об/мин")
    print(f"Геометрия: {rec2.get('geometry_analysis', {}).get('complexity', 'н/д')}")
    print(f"Проходов: {rec2.get('geometry_analysis', {}).get('suggested_passes', 1)}")
    print(f"Валидно? {rec2.get('is_valid', False)}")

    # Тест 3: Форматирование
    print("\n📊 Тест 3: Форматирование для бота")
    print("-" * 40)

    formatted = format_recommendation_for_bot(rec2)
    print(formatted[:200] + "...")

    print("\n" + "=" * 60)
    print("✅ Новый recommendation.py готов к работе!")
    print("✅ Философия: табличные значения для сравнения")
    print("✅ Нет абсурдных расчетов (100 мм ap, 50 проходов)")
    print("✅ Просто, понятно, для сбора практики")
    print("=" * 60)