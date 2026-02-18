"""
СЕРВИС СОХРАНЕНИЯ ИНСТРУМЕНТОВ.
Сохраняет неизвестные инструменты в БД со всеми характеристиками.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ToolSaver:
    """
    Сервис для сохранения инструментов в базу данных.
    """
    
    def __init__(self, session: Session):
        """
        Инициализация сервиса сохранения инструментов.
        
        Args:
            session: SQLAlchemy сессия
        """
        self.session = session
    
    def save_unknown_tool(
        self,
        tool_name: str,
        tool_type: Optional[str] = None,
        insert_material: Optional[str] = None,
        insert_grade: Optional[str] = None,
        insert_radius_mm: Optional[float] = None,
        tool_overhang_mm: Optional[float] = None,
        manufacturer: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Сохранить неизвестный инструмент в БД.
        
        Args:
            tool_name: Название инструмента (CNMG, WNMG и т.д.)
            tool_type: Тип инструмента
            insert_material: Материал пластины
            insert_grade: Марка/градация
            insert_radius_mm: Радиус пластины (мм)
            tool_overhang_mm: Вылет инструмента (мм)
            manufacturer: Производитель
            additional_info: Дополнительная информация
            
        Returns:
            ID сохраненного инструмента или None при ошибке
        """
        if not tool_name or not str(tool_name).strip():
            logger.warning("save_unknown_tool called with empty or None tool_name, skipping")
            return None
        try:
            from app.storage.models import ToolRecord, ToolLibrary
            
            # Проверяем, не существует ли уже такой инструмент
            existing = self.session.query(ToolRecord).filter_by(
                tool_type=tool_type or tool_name
            ).first()
            
            if existing:
                logger.info(f"Tool {tool_name} already exists in DB: {existing.id}")
                return existing.id
            
            # Определяем тип инструмента если не указан
            if not tool_type:
                tool_type = self._determine_tool_type_from_name(tool_name)
            
            # Определяем материал если не указан
            if not insert_material:
                insert_material = self._determine_material_from_grade(insert_grade)
            
            # Создаем запись в ToolRecord
            tool_record = ToolRecord(
                tool_type=tool_type or tool_name,
                insert_material=insert_material or 'твердый сплав',  # По умолчанию
                insert_grade=insert_grade,
                insert_radius_mm=insert_radius_mm or 0.8,  # По умолчанию
                tool_overhang_mm=tool_overhang_mm or 30.0,  # По умолчанию
            )
            
            self.session.add(tool_record)
            self.session.flush()  # Получаем ID
            
            # Также сохраняем в ToolLibrary для справочника
            tool_library = ToolLibrary(
                tool_type=tool_type or tool_name,
                manufacturer=manufacturer,
                model=tool_name,
                recommended_params=additional_info or {}
            )
            
            # Устанавливаем ограничения на основе типа инструмента
            if insert_radius_mm:
                tool_library.max_depth_of_cut_mm = insert_radius_mm * 2.0
                tool_library.max_feed_mm_rev = insert_radius_mm * 0.5
            
            if tool_overhang_mm:
                tool_library.recommended_overhang_mm = tool_overhang_mm
            
            self.session.add(tool_library)
            self.session.commit()
            
            logger.info(f"Saved unknown tool: {tool_name} (ID: {tool_record.id})")
            return tool_record.id
        
        except Exception as e:
            logger.error(f"Error saving tool {tool_name}: {e}", exc_info=True)
            self.session.rollback()
            return None
    
    def save_tool_from_image(
        self,
        image_parse_result: Dict[str, Any]
    ) -> Optional[int]:
        """
        Сохранить инструмент из результата парсинга изображения.
        
        Args:
            image_parse_result: Результат парсинга изображения
            
        Returns:
            ID сохраненного инструмента или None
        """
        if not image_parse_result.get('success'):
            return None
        
        return self.save_unknown_tool(
            tool_name=image_parse_result.get('tool_name'),
            tool_type=image_parse_result.get('tool_type'),
            insert_material=image_parse_result.get('insert_material'),
            insert_grade=image_parse_result.get('insert_grade'),
            insert_radius_mm=image_parse_result.get('insert_radius'),
            manufacturer=image_parse_result.get('manufacturer'),
            additional_info={
                'extracted_text': image_parse_result.get('extracted_text'),
                'confidence': image_parse_result.get('confidence'),
                'source': 'image_ocr'
            }
        )
    
    def _determine_tool_type_from_name(self, tool_name: str) -> str:
        """
        Определить тип инструмента по названию.
        
        Args:
            tool_name: Название инструмента (CNMG, WNMG и т.д.)
            
        Returns:
            Тип инструмента
        """
        if tool_name is None or not str(tool_name).strip():
            return "неизвестный"
        tool_upper = str(tool_name).strip().upper()
        
        # Определяем форму по первой букве
        shape_map = {
            'C': 'ромбическая 80°',
            'W': 'треугольная 60°',
            'T': 'треугольная',
            'D': 'ромбическая 55°',
            'V': 'ромбическая 35°',
            'S': 'квадратная',
            'A': 'треугольная для фрезерования',
            'P': 'треугольная для фрезерования'
        }
        
        shape = shape_map.get(tool_upper[0] if tool_upper else '', 'неизвестная форма')
        
        # Определяем тип по второй букве
        if 'N' in tool_upper or 'M' in tool_upper:
            return f'токарный проходной ({shape})'
        elif 'C' in tool_upper[1:3]:
            return f'токарный чистовой ({shape})'
        elif 'B' in tool_upper or 'P' in tool_upper:
            return f'фрезерный инструмент ({shape})'
        else:
            return f'токарный инструмент ({shape})'
    
    def _determine_material_from_grade(self, grade: Optional[str]) -> Optional[str]:
        """
        Определить материал по марке/градации.
        
        Args:
            grade: Марка/градация инструмента
            
        Returns:
            Материал или None
        """
        if not grade:
            return None
        
        grade_upper = grade.upper()
        
        # Маппинг марок на материалы
        # P-марки обычно для стали, M для нержавейки, K для чугуна
        if grade_upper.startswith('P'):
            return 'твердый сплав'
        elif grade_upper.startswith('M'):
            return 'твердый сплав'
        elif grade_upper.startswith('K'):
            return 'твердый сплав'
        elif 'CERAMIC' in grade_upper or 'CER' in grade_upper:
            return 'керамика'
        elif 'CBN' in grade_upper:
            return 'cbn'
        elif 'DIAMOND' in grade_upper or 'PCD' in grade_upper:
            return 'алмаз'
        
        return None
