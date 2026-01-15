"""
Intent Parser - распознаёт намерения и извлекает данные
НЕ меняет состояние диалога!
"""

import re
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class IntentResult:
    """Результат распознавания намерения."""
    intent: str  # 'provide_data', 'correction', 'question', 'feedback'
    confidence: float
    data: Dict[str, Any]  # Извлеченные данные
    original_text: str


class IntentParser:
    """Парсер намерений - только извлекает, НЕ меняет состояние."""

    def __init__(self):
        # Паттерны для материалов
        self.material_patterns = {
            r'(?:сталь|steel|45|40x|ст)': 'сталь',
            r'(?:алюмин|ал|aluminum|al)': 'алюминий',
            r'(?:титан|тит|titanium|ti)': 'титан',
            r'(?:нерж|нержавейка|stainless|304)': 'нержавеющая сталь',
            r'(?:латунь|brass)': 'латунь',
            r'(?:медь|copper|cu)': 'медь',
            r'(?:чугун|cast iron)': 'чугун',
        }

        # Паттерны для операций
        self.operation_patterns = {
            r'(?:токар|обточ|turn|lathe)': 'токарная',
            r'(?:фрезер|mill|фреза|endmill)': 'фрезерная',
            r'(?:расточ|boring)': 'расточная',
            r'(?:сверл|drill)': 'сверление',
            r'(?:нарез|thread)': 'нарезание резьбы',
            r'(?:чернов|rough)': 'черновая',
            r'(?:чистов|finish)': 'чистовая',
        }

        # Паттерны для чисел и размеров
        self.number_pattern = r'(\d+[.,]?\d*)\s*(?:мм|mm|Ø|диаметр)?'

        # Паттерны для целей обработки
        self.goal_patterns = [
            r'с\s*(\d+[.,]?\d*)\s*(?:до|→|на|->)\s*(\d+[.,]?\d*)',  # с X до Y
            r'от\s*(\d+[.,]?\d*)\s*до\s*(\d+[.,]?\d*)',  # от X до Y
            r'(\d+[.,]?\d*)\s*-\s*(\d+[.,]?\d*)',  # X-Y
        ]

        # Паттерны для чистоты
        self.roughness_pattern = r'(?:Ra|чистот[аы]?|roughness|RA)\s*[=: ]?\s*(\d+[.,]?\d*)\s*(?:мкм|μ|microns)?'

        # Интенты
        self.intent_patterns = {
            'provide_data': [
                r'^[^?]*$',  # Любое утверждение без вопроса
            ],
            'correction': [
                r'не(?: так|правильно| подходит)?',
                r'исправь',
                r'друг[аяой]',
                r'нет[,!]',
                r'не то',
                r'не та',
                r'не те',
                r'не тот',
            ],
            'feedback': [
                r'где\??',
                r'что дальше\??',
                r'а где\??',
                r'так и где\??',
                r'а что\??',
            ],
            'question': [
                r'\?',
                r'как[ойие]?',
                r'что[бы]?',
                r'почему',
                r'зачем',
                r'можно ли',
                r'можно\??',
                r'какие',
                r'сколько',
            ],
            'command': [
                r'^/help',
                r'^/start',
                r'^/reset',
                r'^/context',
            ],
            'affirmation': [
                r'да[,!]?',
                r'верно',
                r'правильно',
                r'подходит',
                r'ок',
                r'хорошо',
                r'понял',
                r'ясно',
            ]
        }

    def parse(self, text: str) -> IntentResult:
        """Распознает намерение и извлекает данные."""
        text_lower = text.strip().lower()
        original_text = text

        # Определяем интент
        intent, intent_confidence = self._detect_intent(text_lower)

        # Извлекаем данные
        data = self._extract_data(text_lower)

        return IntentResult(
            intent=intent,
            confidence=intent_confidence,
            data=data,
            original_text=original_text
        )

    def _detect_intent(self, text: str) -> Tuple[str, float]:
        """Определяет намерение пользователя."""
        # Проверяем команды
        for pattern in self.intent_patterns['command']:
            if re.search(pattern, text, re.IGNORECASE):
                return 'command', 0.95

        # Проверяем вопросы
        if '?' in text:
            for pattern in self.intent_patterns['question']:
                if re.search(pattern, text, re.IGNORECASE):
                    return 'question', 0.8

        # Проверяем обратную связь
        for pattern in self.intent_patterns['feedback']:
            if re.search(pattern, text, re.IGNORECASE):
                return 'feedback', 0.9

        # Проверяем исправления
        for pattern in self.intent_patterns['correction']:
            if re.search(pattern, text, re.IGNORECASE):
                return 'correction', 0.85

        # Проверяем подтверждения
        for pattern in self.intent_patterns['affirmation']:
            if re.search(pattern, text, re.IGNORECASE):
                return 'affirmation', 0.7

        # По умолчанию - предоставление данных
        return 'provide_data', 0.6

    def _extract_data(self, text: str) -> Dict[str, Any]:
        """Извлекает данные из текста."""
        data = {
            'material': None,
            'material_confidence': 0,
            'operation': None,
            'operation_confidence': 0,
            'diameter': None,
            'diameter_confidence': 0,
            'surface_roughness': None,
            'modes': [],
            'start_diameter': None,
            'target_diameter': None,
            'original_text': text
        }

        # Извлекаем материал
        for pattern, material in self.material_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                data['material'] = material
                data['material_confidence'] = 0.9
                break

        # Извлекаем операцию
        for pattern, operation in self.operation_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                data['operation'] = operation
                data['operation_confidence'] = 0.9
                break

        # Извлекаем диаметры
        diameters = self._extract_diameters(text)
        if diameters:
            if len(diameters) == 1:
                data['diameter'] = diameters[0]
                data['diameter_confidence'] = 0.8
            elif len(diameters) == 2:
                data['start_diameter'] = diameters[0]
                data['target_diameter'] = diameters[1]
                data['diameter'] = diameters[1]  # Текущий = целевой
                data['diameter_confidence'] = 0.9

        # Извлекаем чистоту поверхности
        roughness = self._extract_roughness(text)
        if roughness:
            data['surface_roughness'] = roughness
            if 'чист' in text:
                data['modes'].append('чистовая')

        # Определяем режимы
        if 'чернов' in text:
            data['modes'].append('черновая')
        if 'чистов' in text:
            data['modes'].append('чистовая')

        # Если есть чистота, но нет режима
        if data['surface_roughness'] and 'чистовая' not in data['modes']:
            data['modes'].append('чистовая')

        return data

    def _extract_diameters(self, text: str) -> List[float]:
        """Извлекает диаметры из текста."""
        diameters = []

        # Пробуем найти цель обработки
        for pattern in self.goal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    start = float(match.group(1).replace(',', '.'))
                    target = float(match.group(2).replace(',', '.'))
                    return [start, target]
                except:
                    pass

        # Ищем отдельные числа
        matches = re.findall(r'\b(\d+[.,]?\d*)\b', text)
        for match in matches:
            try:
                value = float(match.replace(',', '.'))
                # Фильтруем слишком большие/маленькие числа для диаметров
                if 0.1 <= value <= 1000:
                    diameters.append(value)
            except:
                pass

        return diameters[:2]  # Возвращаем не более 2 диаметров

    def _extract_roughness(self, text: str) -> Optional[float]:
        """Извлекает чистоту поверхности."""
        match = re.search(self.roughness_pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except:
                pass

        # Проверяем упоминания
        if 'ra' in text:
            # Ищем число после ra
            ra_match = re.search(r'ra\s*(\d+[.,]?\d*)', text, re.IGNORECASE)
            if ra_match:
                try:
                    return float(ra_match.group(1).replace(',', '.'))
                except:
                    pass

        return None

    def parse_correction(self, text: str) -> Dict[str, Any]:
        """Специальный парсер для исправлений."""
        correction_data = {
            'type': None,
            'parameter': None,
            'value': None,
            'unit': None
        }

        text_lower = text.lower()

        # Определяем тип исправления
        if any(word in text_lower for word in ['подач', 'feed']):
            correction_data['type'] = 'feed_correction'
            correction_data['parameter'] = 'feed'
        elif any(word in text_lower for word in ['оборот', 'скорость', 'rpm', 'скорост']):
            correction_data['type'] = 'speed_correction'
            correction_data['parameter'] = 'speed'
        elif any(word in text_lower for word in ['глубин', 'depth']):
            correction_data['type'] = 'depth_correction'
            correction_data['parameter'] = 'depth_of_cut'
        elif any(word in text_lower for word in ['инструмент', 'tool']):
            correction_data['type'] = 'tool_correction'
            correction_data['parameter'] = 'tool'

        # Извлекаем значение
        value_match = re.search(r'(\d+[.,]?\d*)', text)
        if value_match:
            try:
                correction_data['value'] = float(value_match.group(1).replace(',', '.'))
            except:
                pass

        # Определяем единицы измерения
        if 'мм/об' in text_lower or 'мм/мин' in text_lower:
            correction_data['unit'] = 'mm'
        elif 'м/мин' in text_lower:
            correction_data['unit'] = 'm/min'
        elif 'об/мин' in text_lower or 'rpm' in text_lower:
            correction_data['unit'] = 'rpm'

        return correction_data


# Глобальный парсер
_intent_parser = IntentParser()


def get_intent_parser() -> IntentParser:
    """Возвращает глобальный парсер."""
    return _intent_parser


def parse_intent(text: str) -> IntentResult:
    """Упрощенный интерфейс для парсинга."""
    return _intent_parser.parse(text)


# Быстрые проверки
def is_correction(text: str) -> bool:
    """Проверяет, является ли текст исправлением."""
    result = parse_intent(text)
    return result.intent == 'correction'


def is_question(text: str) -> bool:
    """Проверяет, является ли текст вопросом."""
    result = parse_intent(text)
    return result.intent == 'question'


def is_feedback(text: str) -> bool:
    """Проверяет, является ли текст обратной связью."""
    result = parse_intent(text)
    return result.intent == 'feedback'


def is_command(text: str) -> bool:
    """Проверяет, является ли текст командой."""
    result = parse_intent(text)
    return result.intent == 'command'


# Тестирование
if __name__ == "__main__":
    parser = IntentParser()

    test_cases = [
        "токарка алюминия диаметр 50",
        "титан с 200 до 150 чистота 0.8",
        "фрезеровка стали 45 чистовая",
        "нет, подача 0.3 слишком большая",
        "где?",
        "а что по скорости?",
        "/help",
        "да, верно"
    ]

    print("🧪 Тестирование Intent Parser")
    print("=" * 60)

    for test in test_cases:
        result = parser.parse(test)
        print(f"\n📝 Ввод: '{test}'")
        print(f"   🎯 Интент: {result.intent} (уверенность: {result.confidence:.2f})")
        if result.data.get('material'):
            print(f"   📦 Материал: {result.data['material']}")
        if result.data.get('operation'):
            print(f"   ⚙️  Операция: {result.data['operation']}")
        if result.data.get('diameter'):
            print(f"   📏 Диаметр: {result.data['diameter']}")
        if result.data.get('start_diameter'):
            print(f"   🎯 Цель: с {result.data['start_diameter']} до {result.data['target_diameter']}")
        if result.data.get('surface_roughness'):
            print(f"   ✨ Чистота: Ra {result.data['surface_roughness']}")
        if result.data.get('modes'):
            print(f"   🔧 Режимы: {result.data['modes']}")

    print("\n" + "=" * 60)
    print("✅ Intent Parser готов к работе!")