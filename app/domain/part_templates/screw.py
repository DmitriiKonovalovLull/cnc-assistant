"""
Шаблон для винтов - типовые параметры и характеристики.
"""

SCREW_TEMPLATE = {
    "part_type": "screw",
    "name_ru": "Винт",
    "name_en": "Screw",
    
    # Типовые диаметры
    "diameters": ["M3", "M4", "M5", "M6", "M8", "M10", "M12"],
    
    # Типовые длины (мм)
    "lengths": {
        "min": 10,
        "max": 100,
        "typical": [10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 100]
    },
    
    # Материал по умолчанию
    "default_material": "сталь",
    "typical_materials": ["сталь 35", "сталь 40Х", "латунь", "нержавейка"],
    
    # Типовые операции обработки
    "operations": ["токарная", "нарезание резьбы", "фрезерование шлица"],
    
    # Типовые режимы обработки
    "typical_modes": {
        "roughing": True,
        "finishing": True,
        "threading": True
    },
    
    # Характеристики
    "machining_characteristics": {
        "head_type": "цилиндрическая",
        "slot_type": "крестообразный",
        "thread_pitch": "стандартный"
    }
}
