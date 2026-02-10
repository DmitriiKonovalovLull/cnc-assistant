"""
НОРМАЛИЗАТОР СТАНКОВ.
Преобразует различные названия станков в стандартные.
"""

from typing import Dict, Optional


class MachineNormalizer:
    """Нормализатор названий станков."""
    
    # Маппинг различных названий в стандартные
    MACHINE_MAP: Dict[str, str] = {
        # Токарные ЧПУ
        'токарный чпу': 'токарный ЧПУ',
        'токарный cnc': 'токарный ЧПУ',
        'токарный с чпу': 'токарный ЧПУ',
        'cnc turning': 'токарный ЧПУ',
        'токарка чпу': 'токарный ЧПУ',
        
        # Токарные ручные
        'токарный ручной': 'токарный ручной',
        'токарный обычный': 'токарный ручной',
        'manual turning': 'токарный ручной',
        'токарка ручная': 'токарный ручной',
        
        # Фрезерные ЧПУ
        'фрезерный чпу': 'фрезерный ЧПУ',
        'фрезерный cnc': 'фрезерный ЧПУ',
        'фрезерный с чпу': 'фрезерный ЧПУ',
        'cnc milling': 'фрезерный ЧПУ',
        'фрезерка чпу': 'фрезерный ЧПУ',
        
        # Фрезерные ручные
        'фрезерный ручной': 'фрезерный ручной',
        'фрезерный обычный': 'фрезерный ручной',
        'manual milling': 'фрезерный ручной',
        'фрезерка ручная': 'фрезерный ручной'
    }
    
    @classmethod
    def normalize(cls, machine_name: str) -> str:
        """
        Нормализовать название станка.
        
        Args:
            machine_name: Исходное название
            
        Returns:
            Нормализованное название
        """
        machine_lower = machine_name.lower().strip()
        
        # Прямой поиск
        if machine_lower in cls.MACHINE_MAP:
            return cls.MACHINE_MAP[machine_lower]
        
        # Поиск по частичному совпадению
        for key, normalized in cls.MACHINE_MAP.items():
            if key in machine_lower or machine_lower in key:
                return normalized
        
        return machine_lower
    
    @classmethod
    def get_machine_category(cls, machine_name: str) -> str:
        """
        Получить категорию станка.
        
        Args:
            machine_name: Название станка
            
        Returns:
            Категория (turning_cnc, turning_manual, milling_cnc, milling_manual)
        """
        normalized = cls.normalize(machine_name)
        
        if 'токарный чпу' in normalized.lower():
            return 'turning_cnc'
        elif 'токарный ручной' in normalized.lower():
            return 'turning_manual'
        elif 'фрезерный чпу' in normalized.lower():
            return 'milling_cnc'
        elif 'фрезерный ручной' in normalized.lower():
            return 'milling_manual'
        
        return 'unknown'
