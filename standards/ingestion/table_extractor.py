"""
Извлечение таблиц из текста: выделение блоков таблиц по структуре (столбцы, строки).
Только извлечение, без интерпретации.
"""

import re
from typing import List, Dict, Any


def find_table_blocks(text: str) -> List[str]:
    """
    Найти в тексте блоки, похожие на таблицы (несколько подряд идущих строк
    с повторяющимся количеством разделителей/колонок).
    Возвращает список строк — кандидаты в таблицы (по строкам).
    """
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    if len(lines) < 2:
        return []

    # Простая эвристика: строки с табуляцией или множеством пробелов между числами/словами
    def looks_like_table_row(line: str) -> bool:
        if "\t" in line:
            return True
        # Несколько чисел в строке
        parts = re.split(r"\s{2,}|\t", line)
        return len(parts) >= 2

    blocks: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        if looks_like_table_row(line):
            current.append(line)
        else:
            if len(current) >= 2:
                blocks.append(current)
            current = []
    if len(current) >= 2:
        blocks.append(current)

    return ["\n".join(block) for block in blocks]


def parse_table_lines(block: str, sep: str = r"\s{2,}|\t") -> List[Dict[str, Any]]:
    """
    Разобрать блок таблицы в список строк-словарей (по первой строке как заголовкам).
    sep — разделитель колонок (регулярка).
    """
    lines = [s.strip() for s in block.splitlines() if s.strip()]
    if not lines:
        return []
    header = re.split(sep, lines[0])
    header = [h.strip() for h in header if h.strip()]
    rows = []
    for line in lines[1:]:
        cells = re.split(sep, line, maxsplit=len(header) - 1)
        cells = [c.strip() for c in cells]
        row = dict(zip(header, cells + [""] * (len(header) - len(cells))))
        rows.append(row)
    return rows
