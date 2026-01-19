import math
from memory.session import get_session

# Скорости резания (Vc, м/мин) для разных материалов (токарка/фрезеровка)
MATERIAL_VC = {
    "aluminum": 200,
    "steel": 80,
    "titanium": 50,
    "stainless_steel": 60,
    "cast_iron": 70,
    "brass": 180,
    "copper": 150,
}


def recommend_rpm(material_id: str, machine_type: str, diameter: float) -> str:
    """
    Рекомендует RPM по материалу и диаметру с учётом типа станка и макс. оборотов.
    """
    session = get_session(1)  # Можно заменить на переданный user_id, если нужно
    max_rpm_turning = session.get("max_rpm_turning", 3000)
    max_rpm_milling = session.get("max_rpm_milling", 12000)

    # Получаем Vc
    Vc = MATERIAL_VC.get(material_id, 80)  # по умолчанию 80 м/мин

    # Расчёт RPM
    rpm = (1000 * Vc) / (math.pi * diameter)

    if machine_type == "manual":
        rpm = min(rpm, max_rpm_turning)
    else:
        rpm = min(rpm, max_rpm_milling)

    rpm = round(rpm)

    return (f"Материал: {material_id}\n"
            f"Диаметр: {diameter} мм\n"
            f"Станок: {'ЧПУ' if machine_type == 'cnc' else 'универсальный'}\n"
            f"Скорость резания Vc: {Vc} м/мин\n"
            f"Рекомендуемые обороты (RPM): {rpm} об/мин")
