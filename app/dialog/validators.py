"""
Validators - валидация входных данных пользователя.
Проверка корректности размеров, материалов, операций.
"""

import re
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class Validator:
    """
    Валидатор входных данных.
    """
    
    @staticmethod
    def validate_diameter(value: str, check_range: bool = True) -> Optional[float]:
        """
        Валидировать диаметр.
        
        Args:
            value: Строка с диаметром (например "50", "50.5", "50 мм")
            check_range: Проверять ли диапазон значений
            
        Returns:
            float если валидно, None если невалидно
        """
        if not value:
            return None
        
        # Убираем единицы измерения и пробелы
        cleaned = re.sub(r'[ммmm]', '', str(value).strip(), flags=re.IGNORECASE)
        cleaned = cleaned.replace('Ø', '').replace('ø', '').strip()
        
        try:
            diameter = float(cleaned)
            
            # Проверяем разумные пределы (0.1 - 2000 мм)
            # Уменьшили максимум с 10000 до 2000 для защиты от номеров стандартов
            if check_range:
                if 0.1 <= diameter <= 2000:
                    return diameter
                else:
                    logger.warning(f"Diameter out of range: {diameter}")
                    return None
            else:
                return diameter if diameter > 0 else None
        
        except (ValueError, TypeError):
            logger.warning(f"Invalid diameter format: {value}")
            return None
    
    @staticmethod
    def validate_dimension_range(value: str) -> Optional[Tuple[float, float]]:
        """
        Валидировать диапазон размеров (например "50 до 200").
        
        Требования:
        - Должен быть контекстный маркер: "с", "до", "→", "-", "to"
        - Значения должны быть в разумных пределах (0.1 - 2000 мм)
        
        Args:
            value: Строка с диапазоном
            
        Returns:
            Tuple (from, to) если валидно, None если невалидно
        """
        if not value:
            return None
        
        # Улучшенные паттерны с обязательным контекстным маркером
        # "с 200 до 50", "200-50", "200→50", "200 to 50"
        patterns = [
            r'(?:с|from)\s*(\d+(?:\.\d+)?)\s*(?:до|to|→|-|–)\s*(\d+(?:\.\d+)?)',  # "с 200 до 50"
            r'(\d+(?:\.\d+)?)\s*(?:до|to|→|-|–)\s*(\d+(?:\.\d+)?)',  # "200-50", "200→50"
            r'Ø?\s*(\d+(?:\.\d+)?)\s*(?:до|to|→|-|–)\s*(\d+(?:\.\d+)?)',  # "Ø200→50"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                try:
                    from_val = float(match.group(1))
                    to_val = float(match.group(2))
                    
                    # Проверяем разумные пределы (0.1 - 2000 мм)
                    if from_val < to_val and 0.1 <= from_val <= 2000 and 0.1 <= to_val <= 2000:
                        return (from_val, to_val)
                    elif to_val < from_val and 0.1 <= from_val <= 2000 and 0.1 <= to_val <= 2000:
                        # Разрешаем обратный порядок (от большего к меньшему)
                        return (to_val, from_val)
                    else:
                        logger.warning(f"Invalid dimension range: {from_val} - {to_val}")
                        return None
                
                except (ValueError, TypeError):
                    continue
        
        return None
    
    @staticmethod
    def validate_material(value: str) -> Optional[str]:
        """
        Валидировать материал.
        
        Args:
            value: Название материала
            
        Returns:
            Нормализованное название материала или None
        """
        if not value:
            return None
        
        # Список допустимых материалов
        valid_materials = {
            'алюминий': 'алюминий',
            'aluminum': 'алюминий',
            'сталь': 'сталь',
            'steel': 'сталь',
            'нержавейка': 'нержавеющая сталь',
            'stainless': 'нержавеющая сталь',
            'титан': 'титан',
            'titanium': 'титан',
            'медь': 'медь',
            'copper': 'медь',
            'латунь': 'латунь',
            'brass': 'латунь',
            'бронза': 'бронза',
            'bronze': 'бронза',
            'пластик': 'пластик',
            'plastic': 'пластик',
        }
        
        value_lower = value.lower().strip()
        
        # Проверяем точное совпадение
        if value_lower in valid_materials:
            return valid_materials[value_lower]
        
        # Проверяем частичное совпадение
        for key, normalized in valid_materials.items():
            if key in value_lower:
                return normalized
        
        # Если не найдено, возвращаем как есть (но с предупреждением)
        logger.warning(f"Unknown material: {value}, using as-is")
        return value.strip()
    
    @staticmethod
    def validate_operation(value: str) -> Optional[str]:
        """
        Валидировать операцию.
        
        Args:
            value: Название операции
            
        Returns:
            Нормализованное название операции или None
        """
        if not value:
            return None
        
        valid_operations = {
            'токарка': 'токарная обработка',
            'turning': 'токарная обработка',
            'фрезеровка': 'фрезерная обработка',
            'milling': 'фрезерная обработка',
            'сверление': 'сверление',
            'drilling': 'сверление',
            'нарезка': 'нарезка резьбы',
            'threading': 'нарезка резьбы',
            'шлифовка': 'шлифовка',
            'grinding': 'шлифовка',
        }
        
        value_lower = value.lower().strip()
        
        if value_lower in valid_operations:
            return valid_operations[value_lower]
        
        for key, normalized in valid_operations.items():
            if key in value_lower:
                return normalized
        
        logger.warning(f"Unknown operation: {value}, using as-is")
        return value.strip()
    
    @staticmethod
    def validate_quantity(value: str) -> Optional[int]:
        """
        Валидировать количество.
        
        Args:
            value: Строка с количеством
            
        Returns:
            int если валидно, None если невалидно
        """
        if not value:
            return None
        
        try:
            # Убираем все нецифровые символы кроме минуса
            cleaned = re.sub(r'[^\d]', '', str(value))
            
            if not cleaned:
                return None
            
            quantity = int(cleaned)
            
            if 1 <= quantity <= 1000000:
                return quantity
            else:
                logger.warning(f"Quantity out of range: {quantity}")
                return None
        
        except (ValueError, TypeError):
            logger.warning(f"Invalid quantity format: {value}")
            return None
    
    @staticmethod
    def extract_data_from_message(message: str, allow_dimensions: bool = False, 
                                  has_standard: bool = False) -> Dict[str, Any]:
        """
        Извлечь данные из сообщения пользователя.
        
        Args:
            message: Текст сообщения
            allow_dimensions: Разрешить ли извлечение размеров (только в WAITING_DIMENSIONS)
            has_standard: Есть ли в сообщении стандарт (запрещает извлечение размеров)
            
        Returns:
            Словарь с извлеченными данными
        """
        data = {}
        
        # Если есть стандарт - запрещаем извлечение размеров
        if has_standard:
            allow_dimensions = False
        
        # Извлекаем диапазон размеров ТОЛЬКО если разрешено
        if allow_dimensions:
            dimension_range = Validator.validate_dimension_range(message)
            if dimension_range:
                data['diameter_from'] = dimension_range[0]
                data['diameter_to'] = dimension_range[1]
            
            # Извлекаем отдельные диаметры ТОЛЬКО с контекстом
            # Паттерн требует наличие "мм" или "Ø" перед числом
            diameter_pattern = r'[Øø]\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*мм'
            diameter_match = re.search(diameter_pattern, message, re.IGNORECASE)
            if diameter_match:
                diameter_str = diameter_match.group(1) or diameter_match.group(2)
                diameter = Validator.validate_diameter(diameter_str)
                if diameter:
                    data['diameter_from'] = diameter
        
        # Извлекаем материал
        material_keywords = ['алюминий', 'сталь', 'титан', 'медь', 'латунь', 
                           'aluminum', 'steel', 'titanium', 'copper', 'brass']
        for keyword in material_keywords:
            if keyword.lower() in message.lower():
                material = Validator.validate_material(keyword)
                if material:
                    data['material'] = material
                    break
        
        # Извлекаем операцию
        operation_keywords = ['токарка', 'фрезеровка', 'сверление', 'нарезка',
                            'turning', 'milling', 'drilling', 'threading']
        for keyword in operation_keywords:
            if keyword.lower() in message.lower():
                operation = Validator.validate_operation(keyword)
                if operation:
                    data['operation'] = operation
                    break
        
        # Извлекаем количество
        quantity_pattern = r'(?:количество|quantity|шт|pcs|pcs\.)\s*[:\s]*(\d+)'
        quantity_match = re.search(quantity_pattern, message, re.IGNORECASE)
        if quantity_match:
            quantity = Validator.validate_quantity(quantity_match.group(1))
            if quantity:
                data['quantity'] = quantity
        
        return data
