"""
PDF Parser - парсинг PDF стандартов в структурированный JSON.
Используется для сравнения версий и извлечения данных.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Парсер PDF файлов стандартов.
    Извлекает таблицы и структурированные данные.
    """
    
    def __init__(self):
        """Инициализация парсера."""
        self.table_extractors = []
        self._load_extractors()
    
    def _load_extractors(self):
        """Загрузить экстракторы таблиц."""
        # TODO: Интегрировать с библиотеками типа camelot, tabula-py
        # Пока базовая реализация
        pass
    
    def parse_to_json(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Распарсить PDF в структурированный JSON.
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Словарь с распарсенными данными
        """
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return {}
        
        try:
            result = {
                'file_path': str(pdf_path),
                'file_size': pdf_path.stat().st_size,
                'sections': [],
                'tables': [],
                'parameters': {},
                'metadata': {}
            }
            
            # TODO: Реальная реализация парсинга PDF
            # Использовать библиотеки:
            # - PyPDF2 / pdfplumber для текста
            # - camelot / tabula-py для таблиц
            # - OCR если нужно
            
            logger.warning("PDF parsing not fully implemented - using placeholder")
            
            return result
        
        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_path}: {e}", exc_info=True)
            return {}
    
    def extract_tables(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Извлечь таблицы из PDF.
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Список таблиц в формате JSON
        """
        # TODO: Реальная реализация извлечения таблиц
        return []
    
    def compare_versions(
        self,
        old_json: Dict[str, Any],
        new_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Сравнить две версии стандарта (старую и новую).
        
        Args:
            old_json: JSON старой версии
            new_json: JSON новой версии
            
        Returns:
            Словарь с различиями
        """
        diff = {
            'changed_sections': [],
            'added_sections': [],
            'removed_sections': [],
            'changed_tables': [],
            'changed_parameters': {}
        }
        
        # Сравниваем секции
        old_sections = {s.get('name'): s for s in old_json.get('sections', [])}
        new_sections = {s.get('name'): s for s in new_json.get('sections', [])}
        
        for section_name in set(old_sections.keys()) | set(new_sections.keys()):
            if section_name not in old_sections:
                diff['added_sections'].append(section_name)
            elif section_name not in new_sections:
                diff['removed_sections'].append(section_name)
            elif old_sections[section_name] != new_sections[section_name]:
                diff['changed_sections'].append(section_name)
        
        # Сравниваем таблицы
        old_tables = {t.get('name'): t for t in old_json.get('tables', [])}
        new_tables = {t.get('name'): t for t in new_json.get('tables', [])}
        
        for table_name in set(old_tables.keys()) | set(new_tables.keys()):
            if table_name not in old_tables:
                diff['added_tables'].append(table_name)
            elif table_name not in new_tables:
                diff['removed_tables'].append(table_name)
            elif old_tables[table_name] != new_tables[table_name]:
                diff['changed_tables'].append(table_name)
        
        # Сравниваем параметры
        old_params = old_json.get('parameters', {})
        new_params = new_json.get('parameters', {})
        
        for param_name in set(old_params.keys()) | set(new_params.keys()):
            if param_name not in old_params:
                diff['changed_parameters'][param_name] = {'action': 'added', 'value': new_params[param_name]}
            elif param_name not in new_params:
                diff['changed_parameters'][param_name] = {'action': 'removed', 'value': old_params[param_name]}
            elif old_params[param_name] != new_params[param_name]:
                diff['changed_parameters'][param_name] = {
                    'action': 'changed',
                    'old': old_params[param_name],
                    'new': new_params[param_name]
                }
        
        return diff
    
    def format_diff_report(self, diff: Dict[str, Any]) -> str:
        """
        Форматировать отчет о различиях версий.
        
        Args:
            diff: Словарь с различиями
            
        Returns:
            Отформатированный текст отчета
        """
        lines = ["📊 <b>Отчет об изменениях версии</b>\n"]
        
        if diff.get('changed_sections'):
            lines.append(f"📝 Измененные разделы: {', '.join(diff['changed_sections'])}")
        
        if diff.get('added_sections'):
            lines.append(f"➕ Добавленные разделы: {', '.join(diff['added_sections'])}")
        
        if diff.get('removed_sections'):
            lines.append(f"➖ Удаленные разделы: {', '.join(diff['removed_sections'])}")
        
        if diff.get('changed_tables'):
            lines.append(f"📋 Измененные таблицы: {', '.join(diff['changed_tables'])}")
        
        if diff.get('changed_parameters'):
            lines.append("\n🔧 Измененные параметры:")
            for param, change in diff['changed_parameters'].items():
                if change['action'] == 'changed':
                    lines.append(f"  • {param}: {change['old']} → {change['new']}")
                elif change['action'] == 'added':
                    lines.append(f"  • {param}: +{change['value']}")
                elif change['action'] == 'removed':
                    lines.append(f"  • {param}: -{change['value']}")
        
        if len(lines) == 1:
            lines.append("✅ Изменений не обнаружено")
        
        return "\n".join(lines)
