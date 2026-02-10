"""
Сервис сохранения неизвестных материалов в БД.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MaterialSaver:
    """
    Сервис для сохранения неизвестных материалов в базу данных.
    """
    
    def __init__(self, session: Session):
        """
        Инициализация сервиса сохранения материалов.
        
        Args:
            session: SQLAlchemy сессия
        """
        self.session = session
    
    def save_unknown_material(
        self,
        material_name: str,
        material_type: Optional[str] = None,
        hardness_hb: Optional[float] = None,
        tensile_strength: Optional[float] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Сохранить неизвестный материал в БД.
        
        Args:
            material_name: Название материала (например, "14ХГСА")
            material_type: Тип материала (сталь, алюминий и т.д.)
            hardness_hb: Твердость по Бринеллю
            tensile_strength: Предел прочности
            additional_info: Дополнительная информация
            
        Returns:
            ID сохраненного материала или None при ошибке
        """
        try:
            # Определяем тип материала если не указан
            if not material_type:
                material_type = self._determine_material_type_from_name(material_name)
            
            # Сохраняем в knowledge base (JSON файл)
            # Также можно сохранить в БД если будет таблица для материалов
            material_data = {
                'name': material_name,
                'normalized_name': material_name.lower(),
                'material_type': material_type,
                'hardness_hb': hardness_hb,
                'tensile_strength': tensile_strength,
                **(additional_info or {})
            }
            
            # Сохраняем в JSON файл базы знаний
            self._save_to_knowledge_base(material_data)
            
            logger.info(f"Saved unknown material: {material_name} (type: {material_type})")
            return 1  # Возвращаем успешный статус
        
        except Exception as e:
            logger.error(f"Error saving material {material_name}: {e}", exc_info=True)
            return None
    
    def _determine_material_type_from_name(self, material_name: str) -> str:
        """
        Определить тип материала по названию.
        
        Args:
            material_name: Название материала
            
        Returns:
            Тип материала
        """
        name_lower = material_name.lower()
        
        # Определяем по ключевым словам и паттернам
        if 'сталь' in name_lower or 'steel' in name_lower or any(char.isdigit() for char in material_name):
            # Если есть цифры и буквы - скорее всего марка стали
            if any(char.isdigit() for char in material_name):
                return 'сталь'
            return 'сталь'
        
        elif 'алюмин' in name_lower or 'aluminum' in name_lower or 'ал' in name_lower:
            return 'алюминий'
        
        elif 'нержав' in name_lower or 'stainless' in name_lower:
            return 'нержавейка'
        
        elif 'титан' in name_lower or 'titanium' in name_lower:
            return 'титан'
        
        elif 'чугун' in name_lower or 'cast' in name_lower:
            return 'чугун'
        
        elif 'латунь' in name_lower or 'brass' in name_lower:
            return 'латунь'
        
        elif 'медь' in name_lower or 'copper' in name_lower:
            return 'медь'
        
        # По умолчанию - сталь (самый распространенный)
        return 'сталь'
    
    def _save_to_knowledge_base(self, material_data: Dict[str, Any]) -> None:
        """
        Сохранить материал в базу знаний (JSON файл).
        
        Args:
            material_data: Данные о материале
        """
        try:
            import json
            from pathlib import Path
            
            knowledge_base_path = Path("app/knowledge/knowledge_base/materials.json")
            knowledge_base_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Загружаем существующие материалы
            materials = []
            if knowledge_base_path.exists():
                with open(knowledge_base_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    materials = data.get('materials', [])
            
            # Проверяем, нет ли уже такого материала
            material_exists = any(
                m.get('name', '').lower() == material_data['name'].lower()
                for m in materials
            )
            
            if not material_exists:
                materials.append(material_data)
                
                # Сохраняем обратно
                with open(knowledge_base_path, 'w', encoding='utf-8') as f:
                    json.dump({'materials': materials}, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Material {material_data['name']} added to knowledge base")
        except Exception as e:
            logger.error(f"Failed to save material to knowledge base: {e}", exc_info=True)
