"""
Сервис сохранения неизвестных станков в БД.
Аналогично ToolSaver, но для станков.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MachineSaver:
    """
    Сервис для сохранения неизвестных станков в базу данных.
    """
    
    def __init__(self, session: Session):
        """
        Инициализация сервиса сохранения станков.
        
        Args:
            session: SQLAlchemy сессия
        """
        self.session = session
    
    def save_unknown_machine(
        self,
        machine_name: str,
        machine_type: Optional[str] = None,
        power_kw: Optional[float] = None,
        max_rpm: Optional[float] = None,
        manufacturer: Optional[str] = None,
        model: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Сохранить неизвестный станок в БД.
        
        Args:
            machine_name: Название станка (например, "Гамма 1250")
            machine_type: Тип станка (токарный ЧПУ, фрезерный и т.д.)
            power_kw: Мощность в кВт
            max_rpm: Максимальные обороты
            manufacturer: Производитель
            model: Модель станка
            additional_info: Дополнительная информация
            
        Returns:
            ID сохраненного станка или None при ошибке
        """
        try:
            from app.storage.models import ToolLibrary  # Используем ToolLibrary для станков тоже
            
            # Проверяем, не существует ли уже такой станок
            existing = self.session.query(ToolLibrary).filter_by(
                model=machine_name
            ).first()
            
            if existing:
                logger.info(f"Machine {machine_name} already exists in DB: {existing.id}")
                return existing.id
            
            # Определяем тип станка если не указан
            if not machine_type:
                machine_type = self._determine_machine_type_from_name(machine_name)
            
            # Определяем производителя если не указан
            if not manufacturer:
                manufacturer = self._determine_manufacturer_from_name(machine_name)
            
            # Создаем запись в ToolLibrary (используем для станков тоже)
            machine_record = ToolLibrary(
                tool_type=f"станок_{machine_type}",  # Префикс для станков
                manufacturer=manufacturer,
                model=machine_name or model,
                recommended_params={
                    'power_kw': power_kw,
                    'max_rpm': max_rpm,
                    'machine_type': machine_type,
                    **(additional_info or {})
                }
            )
            
            self.session.add(machine_record)
            self.session.commit()
            
            logger.info(f"Saved unknown machine: {machine_name} (ID: {machine_record.id})")
            return machine_record.id
        
        except Exception as e:
            logger.error(f"Error saving machine {machine_name}: {e}", exc_info=True)
            self.session.rollback()
            return None
    
    def update_machine_params(
        self,
        machine_name: str,
        power_kw: Optional[float] = None,
        max_rpm: Optional[float] = None,
    ) -> bool:
        """
        Обновить мощность и/или макс. обороты у уже сохранённого станка.
        Ищет запись по model (название) и tool_type, начинающемуся с "станок_".
        """
        try:
            from app.storage.models import ToolLibrary
            record = self.session.query(ToolLibrary).filter(
                ToolLibrary.model == machine_name,
                ToolLibrary.tool_type.like("станок_%"),
            ).first()
            if not record:
                return False
            params = dict(record.recommended_params)
            if power_kw is not None:
                params["power_kw"] = power_kw
            if max_rpm is not None:
                params["max_rpm"] = max_rpm
            record.recommended_params = params
            self.session.commit()
            logger.info(f"Updated machine {machine_name}: power_kw={power_kw}, max_rpm={max_rpm}")
            return True
        except Exception as e:
            logger.error(f"Error updating machine {machine_name}: {e}", exc_info=True)
            self.session.rollback()
            return False
    
    def _determine_machine_type_from_name(self, machine_name: str) -> str:
        """
        Определить тип станка по названию.
        
        Args:
            machine_name: Название станка
            
        Returns:
            Тип станка
        """
        name_lower = machine_name.lower()
        
        # Определяем по ключевым словам
        if 'токар' in name_lower or 'turning' in name_lower:
            if 'чпу' in name_lower or 'cnc' in name_lower:
                return 'токарный ЧПУ'
            return 'токарный ручной'
        
        elif 'фрезер' in name_lower or 'milling' in name_lower:
            if 'чпу' in name_lower or 'cnc' in name_lower:
                return 'фрезерный ЧПУ'
            return 'фрезерный ручной'
        
        elif 'сверл' in name_lower or 'drilling' in name_lower:
            return 'сверлильный'
        
        elif 'расточ' in name_lower or 'boring' in name_lower:
            return 'расточной'
        
        # По умолчанию - токарный ЧПУ (самый распространенный)
        return 'токарный ЧПУ'
    
    def _determine_manufacturer_from_name(self, machine_name: str) -> Optional[str]:
        """
        Определить производителя по названию станка.
        
        Args:
            machine_name: Название станка
            
        Returns:
            Производитель или None
        """
        name_upper = machine_name.upper()
        
        # Известные производители станков
        manufacturers = [
            'HAAS', 'MAZAK', 'DMG', 'OKUMA', 'DOOSAN', 'HYUNDAI',
            'FANUC', 'SIEMENS', 'HEIDENHAIN', 'ГАММА', 'GAMMA',
            'СТАНКОИМПОРТ', 'СТАНКОСТРОЙ', 'КРАСНЫЙ ПРОЛЕТАРИЙ',
            'ИЖСТАНКИ', 'СТАНКОМАШ', 'ТВЕРСКОЙ СТАНКОСТРОИТЕЛЬНЫЙ'
        ]
        
        for manufacturer in manufacturers:
            if manufacturer in name_upper:
                return manufacturer
        
        return None
