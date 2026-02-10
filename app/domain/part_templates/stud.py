"""
Шаблон для шпилек - типовые параметры и характеристики.
"""

STUD_TEMPLATE = {
    "part_type": "stud",
    "name_ru": "Шпилька",
    "name_en": "Stud",
    
    # Типовые диаметры
    "diameters": ["M6", "M8", "M10", "M12", "M16", "M20", "M24", "M30"],
    
    # Типовые длины (мм)
    "lengths": {
        "min": 30,
        "max": 200,
        "typical": [30, 40, 50, 60, 70, 80, 100, 120, 140, 160, 180, 200]
    },
    
    # Материал по умолчанию
    "default_material": "сталь",
    "typical_materials": ["сталь 35", "сталь 40Х", "сталь 45"],
    
    # Типовые операции обработки
    "operations": ["токарная", "нарезание резьбы"],
    
    # Типовые режимы обработки
    "typical_modes": {
        "roughing": True,
        "finishing": True,
        "threading": True
    },
    
    # Характеристики
    "machining_characteristics": {
        "thread_both_ends": True,
        "thread_pitch": "стандартный"
    }
}
