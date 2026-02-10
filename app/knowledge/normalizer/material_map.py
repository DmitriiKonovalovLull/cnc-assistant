"""
НОРМАЛИЗАТОР МАТЕРИАЛОВ.
Преобразует различные названия материалов в стандартные.
Например: "14хгса" → STEEL_ALLOY, "12Х18Н10Т" → STAINLESS_STEEL
"""

from typing import Dict, Optional


class MaterialNormalizer:
    """Нормализатор названий материалов."""
    
    # Маппинг различных названий в стандартные
    MATERIAL_MAP: Dict[str, str] = {
        # Сталь углеродистая
        'ст3': 'сталь',
        'ст45': 'сталь',
        'сталь 45': 'сталь',
        'сталь 3': 'сталь',
        'steel': 'сталь',
        
        # Сталь легированная
        '40х': 'сталь',
        '30хгса': 'сталь',
        '14хгса': 'сталь',
        'alloy steel': 'сталь',
        
        # Нержавейка
        '12х18н10т': 'нержавейка',
        '12х18н10т': 'нержавейка',
        'aisi 304': 'нержавейка',
        'aisi 316': 'нержавейка',
        'aisi 321': 'нержавейка',
        'stainless': 'нержавейка',
        'нерж': 'нержавейка',
        'нержавеющая': 'нержавейка',
        
        # Алюминий
        'д16т': 'алюминий',
        'д16': 'алюминий',
        'амг6': 'алюминий',
        'ал': 'алюминий',
        'aluminum': 'алюминий',
        'aluminium': 'алюминий',
        
        # Титан
        'вт1': 'титан',
        'вт6': 'титан',
        'вт8': 'титан',
        'titanium': 'титан',
        
        # Чугун
        'сч20': 'чугун',
        'сч25': 'чугун',
        'cast iron': 'чугун',
        
        # Латунь
        'л63': 'латунь',
        'brass': 'латунь',
        
        # Медь
        'м1': 'медь',
        'copper': 'медь',
        'cu': 'медь'
    }
    
    @classmethod
    def normalize(cls, material_name: str) -> str:
        """
        Нормализовать название материала.
        
        Args:
            material_name: Исходное название
            
        Returns:
            Нормализованное название
        """
        material_lower = material_name.lower().strip()
        
        # Прямой поиск в маппинге
        if material_lower in cls.MATERIAL_MAP:
            return cls.MATERIAL_MAP[material_lower]
        
        # Поиск по частичному совпадению
        for key, normalized in cls.MATERIAL_MAP.items():
            if key in material_lower or material_lower in key:
                return normalized
        
        # Если не найдено, возвращаем как есть (в нижнем регистре)
        return material_lower
    
    @classmethod
    def get_material_group(cls, material_name: str) -> str:
        """
        Получить группу материала.
        
        Args:
            material_name: Название материала
            
        Returns:
            Группа материала (steel, aluminum, stainless_steel, etc.)
        """
        normalized = cls.normalize(material_name)
        
        groups = {
            'сталь': 'steel',
            'алюминий': 'aluminum',
            'нержавейка': 'stainless_steel',
            'титан': 'titanium',
            'чугун': 'cast_iron',
            'латунь': 'brass',
            'медь': 'copper'
        }
        
        return groups.get(normalized, 'unknown')
