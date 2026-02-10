"""
УНИВЕРСАЛЬНЫЙ ПАРСЕР - поиск инструментов, деталей, чертежей, станков.
Объединяет TextParser, ImageParser и DrawingParser для комплексного поиска.
"""

import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

from app.core.parser import TextParser, ParsedData
from app.core.image_parser import ImageParser
from app.core.drawing_parser import DrawingParser, DrawingData

logger = logging.getLogger(__name__)


class UniversalParser:
    """
    Универсальный парсер для поиска инструментов, деталей, чертежей и станков.
    Объединяет возможности текстового парсинга, OCR и парсинга чертежей.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Инициализация универсального парсера.
        
        Args:
            tesseract_cmd: Путь к Tesseract OCR (опционально)
        """
        self.text_parser = TextParser()
        self.image_parser = ImageParser(tesseract_cmd=tesseract_cmd)
        self.drawing_parser = DrawingParser(tesseract_cmd=tesseract_cmd)
    
    def parse(self, 
              text: Optional[str] = None,
              image_data: Optional[bytes] = None,
              is_drawing: bool = False) -> Dict[str, Any]:
        """
        Универсальный парсинг текста и/или изображения.
        
        Args:
            text: Текст для парсинга (опционально)
            image_data: Байты изображения (опционально)
            is_drawing: Флаг, что изображение - это чертеж
            
        Returns:
            Словарь с результатами парсинга
        """
        result = {
            'success': False,
            'text_data': None,
            'image_data': None,
            'drawing_data': None,
            'tools': [],
            'parts': [],
            'machines': [],
            'confidence': 0.0
        }
        
        # 1. Парсинг текста
        if text:
            try:
                parsed_text = self.text_parser.parse(text)
                result['text_data'] = parsed_text.to_dict()
                
                # Извлекаем инструменты из текста
                if parsed_text.tool_name or parsed_text.tool_material:
                    result['tools'].append({
                        'name': parsed_text.tool_name,
                        'material': parsed_text.tool_material,
                        'manufacturer': parsed_text.tool_manufacturer,
                        'grade': parsed_text.tool_grade,
                        'radius': parsed_text.tool_radius,
                        'source': 'text',
                        'confidence': parsed_text.confidence
                    })
                
                # Извлекаем станки из текста
                if parsed_text.machine_type:
                    result['machines'].append({
                        'type': parsed_text.machine_type,
                        'power': parsed_text.machine_power,
                        'source': 'text',
                        'confidence': parsed_text.confidence
                    })
                
                # Извлекаем детали из текста
                if parsed_text.material or parsed_text.diameter_start:
                    result['parts'].append({
                        'material': parsed_text.material,
                        'diameter_start': parsed_text.diameter_start,
                        'diameter_end': parsed_text.diameter_end,
                        'length': parsed_text.length,
                        'source': 'text',
                        'confidence': parsed_text.confidence
                    })
                
                result['confidence'] = max(result['confidence'], parsed_text.confidence)
                result['success'] = True
                
            except Exception as e:
                logger.error(f"Error parsing text: {e}", exc_info=True)
        
        # 2. Парсинг изображения
        if image_data:
            try:
                if is_drawing:
                    # Парсинг чертежа
                    drawing_data = self.drawing_parser.parse_drawing(image_data)
                    result['drawing_data'] = drawing_data.to_dict()
                    
                    # Извлекаем детали из чертежа
                    if drawing_data.part_name or drawing_data.standard:
                        result['parts'].append({
                            'name': drawing_data.part_name,
                            'part_number': drawing_data.part_number,
                            'standard': drawing_data.standard,
                            'material': drawing_data.material,
                            'diameters': drawing_data.diameters,
                            'lengths': drawing_data.lengths,
                            'tolerances': drawing_data.tolerances,
                            'surface_roughness': drawing_data.surface_roughness,
                            'operations': drawing_data.operations,
                            'source': 'drawing',
                            'confidence': drawing_data.confidence
                        })
                    
                    result['confidence'] = max(result['confidence'], drawing_data.confidence)
                    result['success'] = True
                else:
                    # Парсинг изображения инструмента
                    tool_data = self.image_parser.parse_tool_image(image_data)
                    result['image_data'] = tool_data
                    
                    if tool_data.get('success') and tool_data.get('tool_name'):
                        result['tools'].append({
                            'name': tool_data.get('tool_name'),
                            'type': tool_data.get('tool_type'),
                            'material': tool_data.get('insert_material'),
                            'grade': tool_data.get('insert_grade'),
                            'radius': tool_data.get('insert_radius'),
                            'manufacturer': tool_data.get('manufacturer'),
                            'source': 'image',
                            'confidence': tool_data.get('confidence', 0.5)
                        })
                        
                        result['confidence'] = max(
                            result['confidence'],
                            tool_data.get('confidence', 0.5)
                        )
                        result['success'] = True
                
            except Exception as e:
                logger.error(f"Error parsing image: {e}", exc_info=True)
        
        return result
    
    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """
        Поиск инструментов по запросу.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список найденных инструментов
        """
        result = self.parse(text=query)
        return result.get('tools', [])
    
    def search_parts(self, query: str) -> List[Dict[str, Any]]:
        """
        Поиск деталей по запросу.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список найденных деталей
        """
        result = self.parse(text=query)
        return result.get('parts', [])
    
    def search_machines(self, query: str) -> List[Dict[str, Any]]:
        """
        Поиск станков по запросу.
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список найденных станков
        """
        result = self.parse(text=query)
        return result.get('machines', [])
    
    def parse_drawing_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        Парсинг чертежа из изображения.
        
        Args:
            image_data: Байты изображения чертежа
            
        Returns:
            Результат парсинга чертежа
        """
        drawing_data = self.drawing_parser.parse_drawing(image_data)
        return drawing_data.to_dict()
