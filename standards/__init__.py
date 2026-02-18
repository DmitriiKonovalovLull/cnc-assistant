"""
Модуль стандартов для CNC Assistant.
Поддержка всех мировых систем стандартов: ГОСТ, ОСТ, ISO, DIN, GB, JIS, ANSI, BS и др.
"""

from standards.loader import load_all_standards, get_standards_status

__all__ = ["load_all_standards", "get_standards_status"]
