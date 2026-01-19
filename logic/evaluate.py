"""
evaluate.py
Оценка расхождения рекомендаций и выбора оператора
"""

from typing import Optional, Dict


def evaluate_rpm_decision(
    recommended_rpm: int,
    user_rpm: int,
    machine_max_rpm: Optional[int] = None
) -> Dict:
    """
    Оценивает выбор RPM оператором относительно рекомендации
    """

    if recommended_rpm <= 0 or user_rpm <= 0:
        return {
            "valid": False,
            "reason": "invalid_rpm",
            "rpm_ratio": None,
            "machine_limit_hit": False
        }

    rpm_ratio = user_rpm / recommended_rpm

    machine_limit_hit = False
    if machine_max_rpm and user_rpm >= machine_max_rpm * 0.95:
        machine_limit_hit = True

    # Флаги качества решения
    if rpm_ratio < 0.5:
        reason = "too_conservative"
    elif 0.5 <= rpm_ratio < 0.8:
        reason = "conservative"
    elif 0.8 <= rpm_ratio <= 1.2:
        reason = "close_to_recommended"
    elif 1.2 < rpm_ratio <= 1.5:
        reason = "aggressive"
    else:
        reason = "dangerously_high"

    return {
        "valid": True,
        "reason": reason,
        "rpm_ratio": round(rpm_ratio, 3),
        "machine_limit_hit": machine_limit_hit
    }
