"""Анализ вибрации: по фото спектра (OCR) или по введённой частоте; классификация и коррекция режимов."""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_FREQUENCY_TOLERANCE = 0.05
CORRECTION_RESONANCE_RPM = 0.85
CORRECTION_RESONANCE_AP = 0.7
CORRECTION_CHATTER_FEED = 0.85
CORRECTION_IMBALANCE_RPM = 0.9


@dataclass
class SpectrumData:
    """Данные спектра из OCR: пиковая частота, амплитуда, диапазон."""
    peak_freq_hz: float = 0.0
    amplitude: Optional[float] = None
    amplitude_unit: str = ""
    freq_range_min_hz: Optional[float] = None
    freq_range_max_hz: Optional[float] = None
    raw_text: str = ""
    success: bool = False
    error: str = ""


@dataclass
class CurrentModes:
    """Текущие режимы: n, ap, f, z."""
    rpm: float = 0.0
    ap_mm: float = 0.0
    feed_mm_rev: float = 0.0
    teeth_count: int = 1


@dataclass
class VibrationAnalysisResult:
    """Тип проблемы, частоты, скорректированные режимы, рекомендации."""
    problem_type: str = ""
    problem_type_ru: str = ""
    f_measured_hz: float = 0.0
    f_spindle_hz: float = 0.0
    f_tooth_hz: float = 0.0
    tolerance_used: float = 0.05
    new_rpm: Optional[float] = None
    new_ap_mm: Optional[float] = None
    new_feed_mm_rev: Optional[float] = None
    corrections_applied: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    success: bool = False
    error: str = ""


def _extract_spectrum_from_text(text: str) -> SpectrumData:
    """
    Извлечь из OCR-текста пиковую частоту (Hz), амплитуду и диапазон.
    Поддерживаемые форматы: "125.5 Hz", "125 Hz", "12.5 mm/s", "0-500 Hz", "Range: 0-1000".
    """
    result = SpectrumData(raw_text=text)
    if not text or not text.strip():
        result.error = "Нет текста для анализа"
        return result

    # Частота: число + Hz (или Гц)
    freq_patterns = [
        r"(\d+[.,]?\d*)\s*[Hh]z",
        r"(\d+[.,]?\d*)\s*[Гг]ц",
        r"частот[аы]?\s*[:\s]+(\d+[.,]?\d*)",
        r"freq(?:uency)?\s*[:\s]+(\d+[.,]?\d*)",
        r"peak\s*[:\s]+(\d+[.,]?\d*)",
    ]
    frequencies: List[float] = []
    for pat in freq_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                s = m.group(1).replace(",", ".")
                frequencies.append(float(s))
            except ValueError:
                continue
    # Убираем дубликаты и сортируем; пик — обычно наибольшее выделенное число в контексте "Hz"
    if frequencies:
        # Берём максимальную из распознанных как типичную "пиковую" на спектре
        result.peak_freq_hz = max(frequencies)
        result.success = True

    # Диапазон: "0-500", "0 - 1000 Hz", "Range 10–200"
    range_patterns = [
        r"(\d+[.,]?\d*)\s*[-–—]\s*(\d+[.,]?\d*)\s*(?:[Hh]z|[Гг]ц)?",
        r"range\s*[:\s]*(\d+)[\s-]+(\d+)",
        r"диапазон\s*[:\s]*(\d+)[\s-]+(\d+)",
    ]
    for pat in range_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                result.freq_range_min_hz = float(m.group(1).replace(",", "."))
                result.freq_range_max_hz = float(m.group(2).replace(",", "."))
                break
            except ValueError:
                continue

    # Амплитуда: число + mm/s, m/s, g, или просто число перед "amplitude", "амплитуда"
    amp_patterns = [
        r"(\d+[.,]?\d*)\s*mm/s",
        r"(\d+[.,]?\d*)\s*mm\s*/\s*s",
        r"(\d+[.,]?\d*)\s*m/s",
        r"(\d+[.,]?\d*)\s*g\b",
        r"[Aa]mplit(?:ude)?\s*[:\s]+(\d+[.,]?\d*)",
        r"[Аа]мплитуда\s*[:\s]+(\d+[.,]?\d*)",
    ]
    for pat in amp_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                result.amplitude = float(m.group(1).replace(",", "."))
                if "mm/s" in text[m.start():m.end() + 10] or "mm/s" in text:
                    result.amplitude_unit = "mm/s"
                elif "g" in text[m.start():m.end() + 5]:
                    result.amplitude_unit = "g"
                else:
                    result.amplitude_unit = ""
                break
            except ValueError:
                continue

    if not result.success and not result.peak_freq_hz:
        # Попробуем любое число как частоту, если рядом есть "Hz" в тексте
        any_num = re.findall(r"\b(\d{2,5}[.,]?\d*)\b", text)
        if any_num:
            nums = []
            for s in any_num:
                try:
                    nums.append(float(s.replace(",", ".")))
                except ValueError:
                    pass
            if nums:
                result.peak_freq_hz = max(nums)
                result.success = True

    if not result.success:
        result.error = result.error or "Не удалось извлечь частоту (Hz) из изображения"
    return result


def _f_spindle(rpm: float) -> float:
    """Частота вращения шпинделя, Гц: f_spindle = n / 60."""
    if rpm <= 0:
        return 0.0
    return rpm / 60.0


def _f_tooth(f_spindle: float, z: int) -> float:
    """Частота прохождения зубьев: f_tooth = f_spindle * z."""
    if z <= 0:
        z = 1
    return f_spindle * z


def classify_vibration(
    f_measured_hz: float,
    f_spindle_hz: float,
    f_tooth_hz: float,
    tolerance: float = DEFAULT_FREQUENCY_TOLERANCE,
) -> Tuple[str, str]:
    """
    Определить тип проблемы по частотам.

    Returns:
        (problem_type, problem_type_ru)
        problem_type: tooth_excitation | imbalance | structural_resonance
    """
    if f_measured_hz <= 0:
        return "unknown", "Неизвестно (нет измеренной частоты)"

    tol = tolerance if tolerance > 0 else DEFAULT_FREQUENCY_TOLERANCE
    # Проверка на возбуждение зубьями (пик близок к f_tooth)
    if f_tooth_hz > 0 and abs(f_measured_hz - f_tooth_hz) / f_tooth_hz <= tol:
        return "tooth_excitation", "Возбуждение резанием (зубовая частота)"
    # Субгармоника 0.5 * f_tooth — chatter
    if f_tooth_hz > 0 and abs(f_measured_hz - 0.5 * f_tooth_hz) / (0.5 * f_tooth_hz) <= tol:
        return "chatter", "Chatter (субгармоника зубовой частоты)"
    # Дисбаланс — пик на f_spindle
    if f_spindle_hz > 0 and abs(f_measured_hz - f_spindle_hz) / f_spindle_hz <= tol:
        return "imbalance", "Дисбаланс шпинделя/инструмента"
    # Иначе — структурный резонанс
    return "structural_resonance", "Структурный резонанс конструкции"


def _correct_modes(
    problem_type: str,
    rpm: float,
    ap_mm: float,
    feed_mm_rev: float,
    teeth_count: int,
    f_safe_hz: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float], List[str]]:
    """
    Рассчитать скорректированные режимы по типу проблемы.

    f_safe_hz: безопасная частота (для tooth_excitation: n_new = f_safe * 60 / z).
    """
    new_rpm, new_ap, new_feed = None, None, None
    corrections: List[str] = []

    if problem_type == "structural_resonance":
        new_rpm = rpm * CORRECTION_RESONANCE_RPM
        new_ap = ap_mm * CORRECTION_RESONANCE_AP
        corrections.append(f"Резонанс: обороты × {CORRECTION_RESONANCE_RPM}, глубина × {CORRECTION_RESONANCE_AP}")

    elif problem_type == "chatter":
        new_feed = feed_mm_rev * CORRECTION_CHATTER_FEED
        new_ap = ap_mm * CORRECTION_RESONANCE_AP
        new_rpm = rpm * CORRECTION_RESONANCE_RPM
        corrections.append(f"Chatter: подача × {CORRECTION_CHATTER_FEED}, ap × {CORRECTION_RESONANCE_AP}, n × {CORRECTION_RESONANCE_RPM}")

    elif problem_type == "tooth_excitation":
        if f_safe_hz and f_safe_hz > 0 and teeth_count > 0:
            # Смещение частоты: n_new = f_safe * 60 / z
            new_rpm = (f_safe_hz * 60.0) / teeth_count
            corrections.append(f"Возбуждение зубьями: подбор оборотов под безопасную частоту {f_safe_hz:.1f} Гц")
        else:
            # Правило ±20%: сдвиг от зубовой частоты
            new_rpm = rpm * 0.8
            corrections.append("Возбуждение зубьями: снижение оборотов на 20% (задайте f_safe для точного подбора)")

    elif problem_type == "imbalance":
        new_rpm = rpm * CORRECTION_IMBALANCE_RPM
        corrections.append("Дисбаланс: снижение оборотов на 10%; проверьте балансировку инструмента и патрона")

    return new_rpm, new_ap, new_feed, corrections


def _get_recommendations(problem_type: str) -> List[str]:
    """Текстовые рекомендации по типу проблемы."""
    if problem_type == "imbalance":
        return [
            "Проверьте балансировку инструмента и оправки.",
            "Проверьте затяжку патрона и крепление заготовки.",
        ]
    if problem_type == "tooth_excitation":
        return [
            "Измените обороты так, чтобы зубовая частота не совпадала с резонансом (используйте предложенные n_new).",
        ]
    if problem_type == "chatter":
        return [
            "Снизьте глубину резания и/или подачу.",
            "Укоротите вылет инструмента (L/D).",
            "Проверьте закрепление заготовки.",
        ]
    if problem_type == "structural_resonance":
        return [
            "Измените обороты на 15–20% (ниже или выше) для выхода из резонанса.",
            "Снизьте глубину резания.",
            "При возможности увеличьте жёсткость системы (инструмент, крепление).",
        ]
    return []


def analyze_vibration_from_image(
    image_bytes: bytes,
    current_modes: CurrentModes,
    image_parser: Any,
    tool_teeth_count: Optional[int] = None,
    f_safe_hz: Optional[float] = None,
    tolerance: Optional[float] = None,
    db_session: Any = None,
) -> VibrationAnalysisResult:
    """
    Анализ вибрации по фото спектра/FFT/анализатора.

    1) OCR → извлечение частоты (Hz), амплитуды, диапазона.
    2) Расчёт f_spindle = n/60, f_tooth = f_spindle * z.
    3) Классификация: tooth_excitation | imbalance | structural_resonance | chatter.
    4) Коррекция режимов и рекомендации.

    Args:
        image_bytes: Байты изображения (фото спектра/экрана).
        current_modes: Текущие режимы (rpm, ap_mm, feed_mm_rev, teeth_count).
        image_parser: Экземпляр ImageParser с get_text_from_image().
        tool_teeth_count: Число зубьев z (если не задано — из current_modes.teeth_count).
        f_safe_hz: Безопасная частота для коррекции при tooth_excitation (опционально).
        tolerance: Допуск совпадения частоты (0.05 = 5%). Если None — из БД или 0.05.
        db_session: Сессия БД для чтения коэффициента vibration_frequency_tolerance.

    Returns:
        VibrationAnalysisResult с типом проблемы, частотами, новыми режимами и рекомендациями.
    """
    out = VibrationAnalysisResult()
    if not image_bytes:
        out.error = "Нет изображения"
        return out

    # Допуск из БД или по умолчанию
    if tolerance is not None:
        out.tolerance_used = tolerance
    elif db_session:
        try:
            from app.storage.machine_library import CalculationCoefficient
            row = db_session.query(CalculationCoefficient).filter_by(key="vibration_frequency_tolerance").first()
            if row:
                out.tolerance_used = float(row.value)
        except Exception:
            pass

    z = tool_teeth_count if tool_teeth_count is not None else current_modes.teeth_count
    if z <= 0:
        z = 1

    # 1) OCR
    if not image_parser or not getattr(image_parser, "get_text_from_image", None):
        out.error = "OCR не настроен (image_parser.get_text_from_image отсутствует)"
        return out
    text = image_parser.get_text_from_image(image_bytes)
    spectrum = _extract_spectrum_from_text(text)
    if not spectrum.success or spectrum.peak_freq_hz <= 0:
        out.error = spectrum.error or "Не удалось извлечь частоту со спектра"
        return out

    out.f_measured_hz = spectrum.peak_freq_hz

    # 2) Расчётные частоты
    n = current_modes.rpm
    f_spindle = _f_spindle(n)
    f_tooth = _f_tooth(f_spindle, z)
    out.f_spindle_hz = f_spindle
    out.f_tooth_hz = f_tooth

    # 3) Классификация
    problem_type, problem_ru = classify_vibration(
        spectrum.peak_freq_hz, f_spindle, f_tooth, out.tolerance_used
    )
    out.problem_type = problem_type
    out.problem_type_ru = problem_ru

    # 4) Коррекция режимов
    new_rpm, new_ap, new_feed, corrections = _correct_modes(
        problem_type,
        n,
        current_modes.ap_mm,
        current_modes.feed_mm_rev,
        z,
        f_safe_hz=f_safe_hz,
    )
    out.new_rpm = new_rpm
    out.new_ap_mm = new_ap
    out.new_feed_mm_rev = new_feed
    out.corrections_applied = corrections
    out.recommendations = _get_recommendations(problem_type)
    out.success = True
    return out


def analyze_vibration(
    f_measured_hz: float,
    rpm: float,
    teeth_count: int = 1,
    ap_mm: float = 0.0,
    feed_mm_rev: float = 0.0,
    f_safe_hz: Optional[float] = None,
    tolerance: Optional[float] = None,
    db_session: Any = None,
) -> VibrationAnalysisResult:
    """
    Анализ вибрации по введённой частоте (без фото).

    f_spindle = n / 60, f_tooth = f_spindle * z.
    Если |f_measured - f_tooth| < 5% → tooth_excitation.
    Если |f_measured - f_spindle| < 5% → imbalance.
    Иначе → structural_resonance.

    Коррекция: resonance → n*=0.85, ap*=0.7; tooth_excitation → n=(f_safe*60)/z;
    imbalance → n*=0.9.
    """
    out = VibrationAnalysisResult()
    if f_measured_hz <= 0 or rpm <= 0:
        out.error = "Требуются f_measured_hz > 0 и rpm > 0"
        return out

    if tolerance is not None:
        out.tolerance_used = tolerance
    elif db_session:
        try:
            from app.storage.machine_library import CalculationCoefficient
            row = db_session.query(CalculationCoefficient).filter_by(key="vibration_frequency_tolerance").first()
            if row:
                out.tolerance_used = float(row.value)
        except Exception:
            pass

    z = teeth_count if teeth_count >= 1 else 1
    f_spindle = _f_spindle(rpm)
    f_tooth = _f_tooth(f_spindle, z)
    out.f_measured_hz = f_measured_hz
    out.f_spindle_hz = f_spindle
    out.f_tooth_hz = f_tooth

    problem_type, problem_ru = classify_vibration(
        f_measured_hz, f_spindle, f_tooth, out.tolerance_used
    )
    out.problem_type = problem_type
    out.problem_type_ru = problem_ru

    new_rpm, new_ap, new_feed, corrections = _correct_modes(
        problem_type, rpm, ap_mm, feed_mm_rev, z, f_safe_hz=f_safe_hz,
    )
    out.new_rpm = new_rpm
    out.new_ap_mm = new_ap
    out.new_feed_mm_rev = new_feed
    out.corrections_applied = corrections
    out.recommendations = _get_recommendations(problem_type)
    out.success = True
    return out


def extract_spectrum_from_image(image_bytes: bytes, image_parser: Any) -> SpectrumData:
    """
    Только извлечь данные спектра с фото (без расчётов и коррекции).
    Удобно для отладки или пошагового UI.
    """
    if not image_parser or not getattr(image_parser, "get_text_from_image", None):
        return SpectrumData(success=False, error="OCR не настроен")
    text = image_parser.get_text_from_image(image_bytes)
    return _extract_spectrum_from_text(text)
