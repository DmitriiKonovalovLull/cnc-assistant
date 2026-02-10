"""
НОРМАЛИЗАТОР ИНСТРУМЕНТОВ.
Преобразует различные названия инструментов в стандартные.
Например: "CNMG" ↔ ISO ↔ народные названия
"""

from typing import Dict, Optional


class ToolNormalizer:
    """Нормализатор названий инструментов."""
    
    # Маппинг различных названий в стандартные
    TOOL_TYPE_MAP: Dict[str, str] = {
        # Токарные инструменты
        'cnmg': 'токарный проходной',
        'tnmg': 'токарный проходной',
        'wnmg': 'токарный проходной',
        'проходной': 'токарный проходной',
        'проходной 80°': 'токарный проходной',
        'проходной (80°)': 'токарный проходной',
        
        'dnmg': 'токарный чистовой',
        'vnmg': 'токарный чистовой',
        'чистовой': 'токарный чистовой',
        'чистовой 80°': 'токарный чистовой',
        'чистовой (80°)': 'токарный чистовой',
        
        'канавочный': 'токарный канавочный',
        'grooving': 'токарный канавочный',
        
        # Фрезерные инструменты
        'фреза': 'фрезерная концевая',
        'концевая': 'фрезерная концевая',
        'end mill': 'фрезерная концевая',
        
        'торцевая': 'фрезерная торцевая',
        'face mill': 'фрезерная торцевая'
    }
    
    TOOL_MATERIAL_MAP: Dict[str, str] = {
        'wc': 'твердый сплав',
        'carbide': 'твердый сплав',
        'твердосплавный': 'твердый сплав',
        'твердосплав': 'твердый сплав',
        
        'hss': 'быстрорез',
        'быстрорежущая': 'быстрорез',
        'быстрорежущая сталь': 'быстрорез',
        
        'ceramic': 'керамика',
        'керамический': 'керамика',
        
        'cbn': 'cbn',
        'кубический нитрид бора': 'cbn',
        
        'diamond': 'алмаз',
        'pcd': 'алмаз'
    }
    
    @classmethod
    def normalize_type(cls, tool_type: str) -> str:
        """
        Нормализовать тип инструмента.
        
        Args:
            tool_type: Исходный тип
            
        Returns:
            Нормализованный тип
        """
        tool_lower = tool_type.lower().strip()
        
        # Прямой поиск
        if tool_lower in cls.TOOL_TYPE_MAP:
            return cls.TOOL_TYPE_MAP[tool_lower]
        
        # Поиск по частичному совпадению
        for key, normalized in cls.TOOL_TYPE_MAP.items():
            if key in tool_lower or tool_lower in key:
                return normalized
        
        return tool_lower
    
    @classmethod
    def normalize_material(cls, tool_material: str) -> str:
        """
        Нормализовать материал инструмента.
        
        Args:
            tool_material: Исходный материал
            
        Returns:
            Нормализованный материал
        """
        material_lower = tool_material.lower().strip()
        
        # Прямой поиск
        if material_lower in cls.TOOL_MATERIAL_MAP:
            return cls.TOOL_MATERIAL_MAP[material_lower]
        
        # Поиск по частичному совпадению
        for key, normalized in cls.TOOL_MATERIAL_MAP.items():
            if key in material_lower or material_lower in key:
                return normalized
        
        return material_lower
