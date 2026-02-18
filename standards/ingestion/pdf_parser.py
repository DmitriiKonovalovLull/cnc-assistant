"""
Парсер PDF: извлечение текста, выделение таблиц, первичное определение категории.
Парсер НЕ принимает решений по смыслу — только извлекает сырьё.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from .text_cleaner import normalize_whitespace, split_into_lines
from .table_extractor import find_table_blocks


class GOSTPdfParser:
    """
    Извлечение текста и структуры из PDF (ГОСТ/ОСТ).
    Без внешних решений: только текст, таблицы, первичная категория по ключевым словам.
    """

    def __init__(self):
        self._pdf_available = False
        try:
            import pypdf  # type: ignore
            self._pdf_available = True
        except ImportError:
            pass

    def extract_text(self, file_path: str) -> str:
        """
        Извлечь текст из PDF.
        Если pypdf недоступен, возвращает пустую строку.
        """
        path = Path(file_path)
        if not path.exists() or not path.suffix.lower() == ".pdf":
            return ""
        if not self._pdf_available:
            return ""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            parts = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
            return "\n".join(parts)
        except Exception:
            return ""

    def find_tables(self, text: str) -> List[str]:
        """Найти в тексте блоки таблиц."""
        return find_table_blocks(text)

    def detect_category(self, text: str) -> str:
        """
        По ключевым словам определить категорию стандарта.
        Не интерпретация — только грубая метка для маршрутизации сырья.
        """
        if not text:
            return "unknown"
        t = text.lower()
        if "резьб" in t or "резьба" in t or "thread" in t or "метрическ" in t:
            return "thread"
        if "посад" in t or "fit" in t or "зазор" in t or "натяг" in t:
            return "fit"
        if "шероховат" in t or "roughness" in t or "ra " in t or "rz " in t:
            return "surface"
        if "допуск" in t or "tolerance" in t or "it6" in t or "it7" in t or "h7" in t or "g6" in t:
            return "tolerance"
        return "unknown"
