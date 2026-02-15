"""
Контекстное извлечение данных из HTML.
Разбиваем страницу на секции (заголовки, таблицы, списки) и применяем regex
только в нужном контексте — чтобы не путать мощность шпинделя с мощностью насоса/освещения.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


def _norm(s: str) -> str:
    return " ".join(s.split()).lower() if s else ""


def _extract_sections_by_headings(soup) -> List[Tuple[str, str]]:
    """
    Разбить документ на секции по заголовкам (h2, h3, dt, th).
    Возвращает список (заголовок_секции, текст_секции).
    """
    if not BS4_AVAILABLE:
        return [("", soup.get_text() if hasattr(soup, "get_text") else str(soup))]
    sections: List[Tuple[str, str]] = []
    current_heading = ""
    current_parts: List[str] = []
    # Итерация по тегам в порядке появления
    for tag in soup.find_all(["h2", "h3", "h4", "dt", "tr", "th", "td", "p", "li", "span"]):
        name = tag.name
        text = tag.get_text(strip=True) if hasattr(tag, "get_text") else ""
        if not text:
            continue
        if name in ("h2", "h3", "h4"):
            if current_parts:
                sections.append((current_heading, " ".join(current_parts)))
            current_heading = _norm(text)
            current_parts = [text]
        elif name == "dt":
            if current_parts:
                sections.append((current_heading, " ".join(current_parts)))
            current_heading = _norm(text)
            current_parts = []
        elif name == "th":
            if current_parts and current_heading:
                sections.append((current_heading, " ".join(current_parts)))
            current_heading = _norm(text)
            current_parts = []
        elif name in ("td", "p", "li", "span"):
            current_parts.append(text)
    if current_parts:
        sections.append((current_heading, " ".join(current_parts)))
    if not sections:
        full = soup.get_text() if hasattr(soup, "get_text") else ""
        sections = [("", full)]
    return sections


def _section_relevant_for(field: str, heading: str) -> bool:
    """Определить, относится ли секция к полю (мощность — только шпиндель/привод и т.д.)."""
    h = heading
    if field == "power":
        # Мощность берём только из контекста шпинделя/главного привода
        return any(k in h for k in (
            "шпиндель", "spindle", "main drive", "главный привод",
            "мощность", "power", "motor", "двигатель", "привод"
        ))
    if field == "max_rpm":
        return any(k in h for k in (
            "оборот", "rpm", "speed", "шпиндель", "spindle", "частота"
        ))
    if field in ("radius", "material", "grade", "vc_min", "vc_max"):
        return any(k in h for k in (
            "радиус", "radius", "материал", "material", "марка", "grade",
            "скорость", "speed", "резан", "cutting", "vc", "режим"
        ))
    return True


def extract_machine_data_context_aware(html: str, _machine_name: str = "") -> Dict[str, Any]:
    """
    Извлечь данные о станке с учётом контекста секций.
    Мощность — только из блока про шпиндель/привод, не из «освещение» или «насос».
    """
    result: Dict[str, Any] = {}
    if not BS4_AVAILABLE:
        return result
    try:
        soup = BeautifulSoup(html, "html.parser")
        sections = _extract_sections_by_headings(soup)
    except Exception as e:
        logger.debug(f"Context extractor parse error: {e}")
        return result
    # Паттерны с привязкой к полю
    power_patterns = [
        r"(?:мощность|power)\s*[:\s]+(\d+[.,]?\d*)\s*(?:кВт|kW)",
        r"(?:шпиндел[ья]|spindle)\s+[^.]*?(\d+[.,]?\d*)\s*(?:кВт|kW)",
        r"(\d+[.,]?\d*)\s*(?:кВт|kW)\s*(?:привод|drive|шпиндел)",
    ]
    rpm_patterns = [
        r"(?:макс[имальные]?\s+)?оборот[ы]?\s*[:\s]+(\d+)",
        r"max(?:imum)?\s*rpm\s*[:\s]+(\d+)",
        r"(\d+)\s*об/мин",
        r"(\d+)\s*rpm",
    ]
    for heading, text in sections:
        if not text:
            continue
        if _section_relevant_for("power", heading):
            for pat in power_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    try:
                        result["power"] = float(m.group(1).replace(",", "."))
                        break
                    except (ValueError, IndexError):
                        pass
            if result.get("power") is not None:
                break
    for heading, text in sections:
        if not text:
            continue
        if _section_relevant_for("max_rpm", heading):
            for pat in rpm_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    try:
                        result["max_rpm"] = float(m.group(1))
                        break
                    except (ValueError, IndexError):
                        pass
            if result.get("max_rpm") is not None:
                break
    # Тип станка — из любой секции
    for _, text in sections:
        m = re.search(r"(?:тип|type)[:\s]+([А-Яа-яA-Za-z0-9\s\-]+?)(?:\s*[;|,]|\s*$)", text, re.IGNORECASE)
        if m:
            result["machine_type"] = m.group(1).strip()[:80]
            break
    return result


def extract_tool_data_context_aware(html: str, _tool_name: str = "") -> Dict[str, Any]:
    """
    Извлечь данные об инструменте по секциям.
    Радиус, материал, марка, vc — из блоков про режущую кромку, материал, режимы.
    """
    result: Dict[str, Any] = {}
    if not BS4_AVAILABLE:
        return result
    try:
        soup = BeautifulSoup(html, "html.parser")
        sections = _extract_sections_by_headings(soup)
    except Exception as e:
        logger.debug(f"Context extractor parse error: {e}")
        return result
    radius_patterns = [
        r"радиус[:\s]+(\d+[.,]?\d*)\s*мм",
        r"radius[:\s]+(\d+[.,]?\d*)\s*mm",
        r"r\s*[=:]\s*(\d+[.,]?\d*)",
    ]
    material_patterns = [
        r"материал[:\s]+([А-Яа-яA-Za-z0-9\s\-]+?)(?:\s*[;|,]|\s*$)",
        r"material[:\s]+([A-Za-z0-9\s\-]+?)(?:\s*[;|,]|\s*$)",
    ]
    grade_patterns = [
        r"марка[:\s]+([A-Z0-9]+)",
        r"grade[:\s]+([A-Z0-9]+)",
    ]
    vc_patterns = [
        r"скорость\s+резания[:\s]+(\d+)[-\s]+(\d+)\s*м/мин",
        r"cutting\s+speed[:\s]+(\d+)[-\s]+(\d+)\s*m/min",
        r"vc[:\s]+(\d+)[-\s]+(\d+)",
    ]
    for heading, text in sections:
        if not text:
            continue
        if _section_relevant_for("radius", heading) and "radius" not in result:
            for pat in radius_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    try:
                        result["radius"] = float(m.group(1).replace(",", "."))
                        break
                    except (ValueError, IndexError):
                        pass
        if _section_relevant_for("material", heading) and "material" not in result:
            for pat in material_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    result["material"] = m.group(1).strip()[:60]
                    break
        if _section_relevant_for("grade", heading) and "grade" not in result:
            for pat in grade_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    result["grade"] = m.group(1).strip()[:40]
                    break
        if _section_relevant_for("vc_min", heading) and "vc_min" not in result:
            for pat in vc_patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    try:
                        result["vc_min"] = float(m.group(1))
                        result["vc_max"] = float(m.group(2))
                        break
                    except (ValueError, IndexError):
                        pass
    return result


def extract_operation_data_context_aware(html: str, _operation_type: str = "", _material: str = "") -> Dict[str, Any]:
    """Режимы резания — ищем в секциях про скорость/режимы."""
    result: Dict[str, Any] = {}
    if not BS4_AVAILABLE:
        return result
    try:
        soup = BeautifulSoup(html, "html.parser")
        sections = _extract_sections_by_headings(soup)
    except Exception as e:
        logger.debug(f"Context extractor parse error: {e}")
        return result
    vc_patterns = [
        r"скорость\s+резания[:\s]+(\d+)[-\s]+(\d+)\s*м/мин",
        r"vc[:\s]+(\d+)[-\s]+(\d+)\s*м/мин",
        r"cutting\s+speed[:\s]+(\d+)[-\s]+(\d+)",
    ]
    for heading, text in sections:
        if not _section_relevant_for("vc_min", heading):
            continue
        for pat in vc_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    result["vc_min"] = float(m.group(1))
                    result["vc_max"] = float(m.group(2))
                    return result
                except (ValueError, IndexError):
                    pass
    return result
