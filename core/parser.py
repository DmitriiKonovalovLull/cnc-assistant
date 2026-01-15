"""
Улучшенный парсер для сложных запросов.
"""

import re


class IntelligentParser:
    """Парсер с улучшенным извлечением чисел и параметров."""

    @staticmethod
    def parse(text):
        text_lower = text.lower().strip()
        result = {}

        # === ОПРЕДЕЛЕНИЕ ЯЗЫКА ПО ЗАПРОСУ ===
        # Проверяем китайские иероглифы
        if re.search(r'[\u4e00-\u9fff]', text):
            result['detected_language'] = 'zh'
        # Проверяем английские слова
        elif any(word in text_lower for word in ['steel', 'aluminum', 'titanium', 'cutting', 'speed', 'feed']):
            result['detected_language'] = 'en'
        else:
            result['detected_language'] = 'ru'

        # === РАСШИРЕННЫЙ СПИСОК МАТЕРИАЛОВ ===
        # Русские названия
        ru_materials = {
            'сталь': 'сталь',
            'сталь 45': 'сталь 45',
            'сталь45': 'сталь 45',
            'сталь 30': 'сталь 30',
            'сталь30': 'сталь 30',
            'сталь 20': 'сталь 20',
            'сталь20': 'сталь 20',
            'сталь 40х': 'сталь 40х',
            'сталь40х': 'сталь 40х',
            'сталь 40хн': 'сталь 40хн',
            'алюминий': 'алюминий',
            'титан': 'титан',
            'титан вт6': 'титан вт6',
            'титанвт6': 'титан вт6',
            'титан вт3': 'титан вт3',
            'нержавейка': 'нержавеющая сталь',
            'нержавеющая': 'нержавеющая сталь',
            'нержавеющая сталь': 'нержавеющая сталь',
            'латунь': 'латунь',
            'медь': 'медь',
            'бронза': 'бронза',
            'чугун': 'чугун',
            'инструментальная сталь': 'инструментальная сталь',
            'пластик': 'пластик',
            'дерево': 'дерево',
        }

        # Английские названия
        en_materials = {
            'steel': 'steel',
            'steel 45': 'steel 45',
            'steel45': 'steel 45',
            'steel 30': 'steel 30',
            'steel30': 'steel 30',
            'carbon steel': 'carbon steel',
            'aluminum': 'aluminum',
            'aluminium': 'aluminum',
            'titanium': 'titanium',
            'stainless steel': 'stainless steel',
            'brass': 'brass',
            'copper': 'copper',
            'bronze': 'bronze',
            'cast iron': 'cast iron',
            'tool steel': 'tool steel',
        }

        # Китайские названия
        zh_materials = {
            '钢': 'steel',
            '45号钢': 'steel 45',
            '30号钢': 'steel 30',
            '铝': 'aluminum',
            '钛': 'titanium',
            '不锈钢': 'stainless steel',
            '黄铜': 'brass',
            '铜': 'copper',
            '青铜': 'bronze',
            '铸铁': 'cast iron',
        }

        # Ищем материал по языку
        material_found = False

        # Сначала русские
        if result['detected_language'] == 'ru':
            for ru_name, value in ru_materials.items():
                if ru_name in text_lower:
                    result['material'] = value
                    result['material_confidence'] = 0.9
                    material_found = True
                    break

        # Английские
        if not material_found and result['detected_language'] in ['ru', 'en']:
            for en_name, value in en_materials.items():
                if en_name in text_lower:
                    result['material'] = value
                    result['material_confidence'] = 0.9
                    material_found = True
                    break

        # Китайские
        if not material_found and result['detected_language'] == 'zh':
            for zh_name, value in zh_materials.items():
                if zh_name in text:
                    result['material'] = value
                    result['material_confidence'] = 0.9
                    material_found = True
                    break

        # === ОПЕРАЦИИ ===
        # Русские
        if any(word in text_lower for word in ['токар', 'точить', 'проточить', 'обточить']):
            result['operation'] = 'токарная'
            result['operation_confidence'] = 0.9

        if any(word in text_lower for word in ['фрез', 'фрезеров', 'фрезу']):
            result['operation'] = 'фрезерная'
            result['operation_confidence'] = 0.9

        if any(word in text_lower for word in ['расточ', 'растачив', 'расточку']):
            result['operation'] = 'расточка'
            result['operation_confidence'] = 0.9

        if any(word in text_lower for word in ['сверл', 'отверстие']):
            result['operation'] = 'сверление'
            result['operation_confidence'] = 0.9

        # === РЕЖИМЫ ===
        modes = []
        if any(word in text_lower for word in ['чернов', 'черн', 'груб', 'съем']):
            modes.append('черновая')

        if any(word in text_lower for word in ['чистов', 'чист', 'финиш', 'точн', 'чистовую']):
            modes.append('чистовая')

        if modes:
            result['modes'] = modes
            result['modes_confidence'] = 0.8

        # === УЛУЧШЕННОЕ ИЗВЛЕЧЕНИЕ ЧИСЕЛ С ПАРАМЕТРАМИ ===
        # Ищем все числа в тексте
        all_numbers = re.findall(r'\b(\d+[.,]?\d*)\b', text_lower)
        numbers = [float(num.replace(',', '.')) for num in all_numbers]

        if numbers:
            result['numbers'] = numbers

            # Пытаемся понять, к каким параметрам относятся числа
            param_patterns = [
                (r'диаметр\s*(\d+[.,]?\d*)', 'diameter'),
                (r'вылет\s*(\d+[.,]?\d*)', 'overhang'),
                (r'ширин[ауы]?\s*(\d+[.,]?\d*)', 'width'),
                (r'глубин[ауы]?\s*(\d+[.,]?\d*)', 'depth'),
                (r'[øØd]\s*(\d+[.,]?\d*)', 'diameter'),  # Ø200 или d200
                (r'(\d+[.,]?\d*)\s*мм', 'general_mm'),  # 200 мм
            ]

            for pattern, param_type in param_patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    value = float(match.group(1).replace(',', '.'))
                    result[param_type] = value
                    result[f'{param_type}_confidence'] = 0.9

            # Если не нашли по шаблонам, но есть 4+ числа - считаем это запросом на расчёт
            if len(numbers) >= 4 and ('расточ' in text_lower or 'токар' in text_lower):
                # Предполагаем порядок: диаметр, вылет, ширина, глубина
                result['diameter'] = numbers[0]
                result['overhang'] = numbers[1]
                result['width'] = numbers[2]
                result['depth'] = numbers[3]
                result['is_calculation_request'] = True

        # === КОМАНДЫ ===
        # Запрос рекомендаций
        advice_words = ['рекомендац', 'совет', 'подскажи', 'параметр', 'режим', 'настрой', 'что делать', 'как']
        if any(word in text_lower for word in advice_words):
            result['intent'] = 'get_advice'

        # Запрос расчёта
        calc_words = ['посчитай', 'рассчитай', 'расчет', 'вычисли', 'какой оборот', 'какая скорость']
        if any(word in text_lower for word in calc_words):
            result['intent'] = 'get_calculation'
            result['is_calculation_request'] = True

        # Языковые команды
        if any(word in text_lower for word in ['английский', 'english', 'en']):
            result['language'] = 'en'
        elif any(word in text_lower for word in ['китайский', 'chinese', '中文', 'zh']):
            result['language'] = 'zh'
        elif any(word in text_lower for word in ['русский', 'russian', 'ru']):
            result['language'] = 'ru'

        return result