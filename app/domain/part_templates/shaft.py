"""
Шаблон для валов - типовые параметры и характеристики.
"""

SHAFT_TEMPLATE = {
    "part_type": "shaft",
    "name_ru": "Вал",
    "name_en": "Shaft",
    
    # Типовые диаметры (мм)
    "diameters": {
        "min": 10,
        "max": 500,
        "typical": [20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300]
    },
    
    # Типовые длины (мм)
    "lengths": {
        "min": 50,
        "max": 2000,
        "typical": [100, 150, 200, 250, 300, 400, 500, 600, 800, 1000]
    },
    
    # Материал по умолчанию
    "default_material": "сталь",
    "typical_materials": ["сталь 45", "сталь 40Х", "сталь 20Х", "сталь 18ХГТ"],
    
    # Типовые операции обработки
    "operations": ["токарная", "шлифование", "фрезерование"],
    
    # Типовые режимы обработки
    "typical_modes": {
        "roughing": True,
        "semi_finishing": True,
        "finishing": True,
        "grinding": True
    },
    
    # Характеристики
    "machining_characteristics": {
        "tolerance": "h7-h9",
        "surface_roughness": "Ra 0.8-3.2"
    }
}
