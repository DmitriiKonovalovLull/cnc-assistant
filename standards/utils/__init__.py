"""Утилиты для работы со стандартами."""

from standards.utils.standard_normalizer import (
    normalize_standard_text,
    parse_standard_designation,
    normalize_standard_number,
    get_search_variants
)

__all__ = [
    'normalize_standard_text',
    'parse_standard_designation',
    'normalize_standard_number',
    'get_search_variants'
]
