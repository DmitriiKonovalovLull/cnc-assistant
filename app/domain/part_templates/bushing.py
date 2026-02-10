"""
Шаблон для втулок - типовые параметры и характеристики.
"""

BUSHING_TEMPLATE = {
    "part_type": "bushing",
    "name_ru": "Втулка",
    "name_en": "Bushing",
    
    # Типовые диаметры (мм)
    "diameters": {
        "min": 10,
        "max": 300,
        "typical": [20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200]
    },
    
    # Типовые длины (мм)
    "lengths": {
        "min": 20,
        "max": 500,
        "typical": [30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300]
    },
    
    # Материал по умолчанию
    "default_material": "сталь",
    "typical_materials": ["сталь 45", "бронза", "латунь", "чугун"],
    
    # Типовые операции обработки
    "operations": ["токарная", "растачивание", "шлифование"],
    
    # Типовые режимы обработки
    "typical_modes": {
        "roughing": True,
        "semi_finishing": True,
        "finishing": True,
        "boring": True
    },
    
    # Характеристики
    "machining_characteristics": {
        "tolerance": "H7-H9",
        "surface_roughness": "Ra 0.8-3.2"
    }
}
