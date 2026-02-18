"""
PDF Parser - парсинг PDF стандартов в структурированный JSON.
Извлекает таблицы, параметры и структурированные данные.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import json

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumber not available, PDF parsing will be limited")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Парсер PDF файлов стандартов.
    Извлекает структурированные данные для хранения в БД.
    """
    
    def __init__(self):
        """Инициализация парсера."""
        if not PDFPLUMBER_AVAILABLE and not PYPDF2_AVAILABLE:
            logger.warning("No PDF libraries available. Install pdfplumber or PyPDF2 for full functionality.")
    
    def parse(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Распарсить PDF файл стандарта.
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Словарь с распарсенными данными:
            {
                "threads": {...},
                "dimensions": {...},
                "tolerances": {...},
                "tables": [...],
                "text": "..."
            }
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        result = {
            'threads': {},
            'dimensions': {},
            'tolerances': {},
            'tables': [],
            'text': '',
            'metadata': {}
        }
        
        try:
            # Используем pdfplumber если доступен (лучше для таблиц)
            if PDFPLUMBER_AVAILABLE:
                result = self._parse_with_pdfplumber(pdf_path)
            elif PYPDF2_AVAILABLE:
                result = self._parse_with_pypdf2(pdf_path)
            else:
                logger.warning("No PDF parser available, returning empty structure")
                result['metadata'] = {
                    'file_path': str(pdf_path),
                    'file_size': pdf_path.stat().st_size,
                    'parser': 'none'
                }
            
            logger.info(f"Parsed PDF: {pdf_path.name}, extracted {len(result.get('tables', []))} tables")
            
        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_path}: {e}", exc_info=True)
            result['error'] = str(e)
        
        return result
    
    def _parse_with_pdfplumber(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Парсинг с использованием pdfplumber (лучше для таблиц).
        
        Args:
            pdf_path: Путь к PDF
            
        Returns:
            Распарсенные данные
        """
        result = {
            'threads': {},
            'dimensions': {},
            'tolerances': {},
            'tables': [],
            'text': '',
            'metadata': {}
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            result['metadata'] = {
                'pages': len(pdf.pages),
                'file_path': str(pdf_path),
                'file_size': pdf_path.stat().st_size,
                'parser': 'pdfplumber'
            }
            
            # Извлекаем текст со всех страниц
            text_parts = []
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    text_parts.append(text)
                
                # Извлекаем таблицы
                tables = page.extract_tables()
                for table_num, table in enumerate(tables, 1):
                    if table:
                        result['tables'].append({
                            'page': page_num,
                            'table_number': table_num,
                            'data': table,
                            'rows': len(table),
                            'cols': len(table[0]) if table else 0
                        })
            
            result['text'] = '\n\n'.join(text_parts)
            
            # Пытаемся извлечь структурированные данные из текста
            self._extract_structured_data(result)
        
        return result
    
    def _parse_with_pypdf2(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Парсинг с использованием PyPDF2 (fallback).
        
        Args:
            pdf_path: Путь к PDF
            
        Returns:
            Распарсенные данные
        """
        result = {
            'threads': {},
            'dimensions': {},
            'tolerances': {},
            'tables': [],
            'text': '',
            'metadata': {}
        }
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            result['metadata'] = {
                'pages': len(pdf_reader.pages),
                'file_path': str(pdf_path),
                'file_size': pdf_path.stat().st_size,
                'parser': 'pypdf2'
            }
            
            # Извлекаем текст
            text_parts = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            result['text'] = '\n\n'.join(text_parts)
            
            # PyPDF2 не умеет извлекать таблицы, только текст
            # Пытаемся извлечь структурированные данные из текста
            self._extract_structured_data(result)
        
        return result
    
    def _extract_structured_data(self, result: Dict[str, Any]) -> None:
        """
        Извлечь структурированные данные из текста.
        Ищет паттерны резьб, размеров, допусков.
        
        Args:
            result: Словарь с результатами парсинга (изменяется in-place)
        """
        text = result.get('text', '')
        
        import re
        
        # Ищем резьбы (M20, M42x1.5, M42x1.5-6g)
        thread_pattern = r'\bM\d+(?:x\d+(?:\.\d+)?)?(?:[-]\d+[ghGH])?\b'
        threads = re.findall(thread_pattern, text)
        if threads:
            result['threads'] = {
                'found': list(set(threads)),
                'count': len(set(threads))
            }
        
        # Ищем допуски (H7, g6, IT7)
        tolerance_pattern = r'\b[HhGg][0-9]\b|\bIT[0-9]+\b'
        tolerances = re.findall(tolerance_pattern, text)
        if tolerances:
            result['tolerances'] = {
                'found': list(set(tolerances)),
                'count': len(set(tolerances))
            }
        
        # Ищем размеры (диаметры, длины)
        dimension_pattern = r'\b\d+[.,]\d+\s*мм\b|\bØ\d+\b|\b\d+\s*×\s*\d+\b'
        dimensions = re.findall(dimension_pattern, text)
        if dimensions:
            result['dimensions'] = {
                'found': list(set(dimensions)),
                'count': len(set(dimensions))
            }
    
    def extract_tables(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Извлечь только таблицы из PDF.
        
        Args:
            pdf_path: Путь к PDF
            
        Returns:
            Список таблиц
        """
        parsed = self.parse(pdf_path)
        return parsed.get('tables', [])
