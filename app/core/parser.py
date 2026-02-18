"""
ПАРСЕР ТЕКСТА - извлекает данные из пользовательского ввода.
НИЧЕГО НЕ РЕШАЕТ - только извлекает материал, диаметры, числа и т.д.
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class ParsedData:
    """Результат парсинга текста."""
    material: Optional[str] = None
    operation: Optional[str] = None
    mode: Optional[str] = None
    diameter_start: Optional[float] = None
    diameter_end: Optional[float] = None
    length: Optional[float] = None
    machine_type: Optional[str] = None
    machine_power: Optional[float] = None
    tool_material: Optional[str] = None
    tool_radius: Optional[float] = None
    tool_overhang: Optional[float] = None
    tool_diameter: Optional[float] = None  # Диаметр инструмента (державки/фрезы)
    tool_name: Optional[str] = None  # Название инструмента (CNMG, WNMG и т.д.)
    tool_manufacturer: Optional[str] = None  # Производитель
    tool_grade: Optional[str] = None  # Марка/градация
    
    # Параметры детали
    thread_size: Optional[str] = None  # Размер резьбы (M6, M12 и т.д.)
    quantity: Optional[int] = None  # Количество деталей
    
    # Числовые параметры режимов
    vc: Optional[float] = None  # м/мин
    rpm: Optional[float] = None  # об/мин
    feed: Optional[float] = None  # мм/об
    ap: Optional[float] = None  # мм
    
    # Метаданные
    parsed_fields: List[str] = None
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.parsed_fields is None:
            self.parsed_fields = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        result = {}
        for field in [
            'material', 'operation', 'mode',
            'diameter_start', 'diameter_end', 'length',
            'machine_type', 'machine_power',
            'tool_material', 'tool_radius', 'tool_overhang',
            'tool_name', 'tool_manufacturer', 'tool_grade',
            'thread_size', 'quantity',
            'vc', 'rpm', 'feed', 'ap',
            'parsed_fields', 'confidence'
        ]:
            value = getattr(self, field, None)
            if value is not None:
                result[field] = value
        return result


class TextParser:
    """Парсер текста пользователя."""
    
    # Словари для распознавания
    MATERIAL_KEYWORDS = {
        'сталь': ['сталь', 'steel', 'железо'],
        'алюминий': ['алюмин', 'aluminum', 'ал', 'д16'],
        'нержавейка': ['нержавей', 'нерж', 'stainless', '12х18н10т', '304', '316'],
        'титан': ['титан', 'titanium', 'тита', 'вт'],
        'чугун': ['чугун', 'cast iron', 'сч'],
        'латунь': ['латунь', 'brass'],
        'медь': ['медь', 'copper', 'cu'],
    }
    # Марки сталей с пробелом (30 хгса → 30ХГСА), чтобы не путать с числом станка
    MATERIAL_STEEL_GRADE_SPACE = re.compile(
        r'\b(\d{1,2})\s*[хХ]\s*([а-яА-Я]{2,10})\b',
        re.IGNORECASE
    )
    # Только известные 4-значные марки (не номера моделей станков вроде 1250)
    VALID_4DIGIT_GRADES = frozenset({
        '1045', '1020', '1008', '4140', '4340', '304', '316', '321', '316l',
        '2024', '6061', '7075', '5083', '5052',
    })
    
    OPERATION_KEYWORDS = {
        'токарка': ['токар', 'точение', 'обтачивание', 'turning'],
        'фрезерование': ['фрезер', 'фреза', 'milling'],
        'сверление': ['сверл', 'drilling'],
        'растачивание': ['расточ', 'boring']
    }
    
    MODE_KEYWORDS = {
        'черновая': ['чернов', 'грубо', 'обдир', 'roughing'],
        'получистовая': ['получист', 'средн', 'semi'],
        'чистовая': ['чистов', 'чисто', 'финиш', 'finishing'],
        'тонкая': ['тонк', 'прецизион', 'precision']
    }
    
    MACHINE_KEYWORDS = {
        'токарный ЧПУ': ['чпу', 'cnc', 'числов', 'токар'],
        'токарный ручной': ['ручной', 'manual', 'обычн'],
        'фрезерный ЧПУ': ['фрезер', 'чпу', 'cnc'],
        'фрезерный ручной': ['фрезер', 'ручной']
    }
    
    TOOL_MATERIAL_KEYWORDS = {
        'твердый сплав': ['тверд', 'сплав', 'carbide', 'wc'],
        'быстрорез': ['быстрорез', 'hss', 'быстрорежущ'],
        'керамика': ['керамик', 'ceramic'],
        'cbn': ['cbn', 'кубический нитрид бора'],
        'алмаз': ['алмаз', 'diamond']
    }
    
    # ISO коды инструментов для токарки
    ISO_TOOL_CODES = [
        'CNMG', 'WNMG', 'TNMG', 'DNMG', 'VNMG', 'SNMG',  # Ромбические и треугольные
        'CCMG', 'DCMG', 'VCMG', 'SCMG',  # Ромбические для чистовой
        'VBMT', 'TBMT', 'CBMT',  # Треугольные
        'TPGN', 'TPGR', 'TPGW',  # Треугольные для фрезерования
        'APMT', 'APKT', 'APGT',  # Треугольные для фрезерования
    ]
    
    # Производители инструментов
    TOOL_MANUFACTURERS = [
        'SANDVIK', 'KENNAMETAL', 'ISCAR', 'SECO', 'WALTER',
        'KYOCERA', 'MITSUBISHI', 'CERATIZIT', 'TUNGALOY',
        'VALENITE', 'SUMITOMO', 'DIJET', 'TAEGUTEC'
    ]
    
    def parse(self, text: str) -> ParsedData:
        """
        Парсить текст пользователя.
        
        Args:
            text: Текст для парсинга
            
        Returns:
            ParsedData с извлеченными данными
        """
        text_lower = text.lower()
        parsed = ParsedData()
        
        # 1. Материал
        parsed.material = self._parse_material(text_lower)
        if parsed.material:
            parsed.parsed_fields.append('material')
        
        # 2. Операция
        parsed.operation = self._parse_operation(text_lower)
        if parsed.operation:
            parsed.parsed_fields.append('operation')
        
        # 3. Режим обработки
        parsed.mode = self._parse_mode(text_lower)
        if parsed.mode:
            parsed.parsed_fields.append('mode')
        
        # 4. Диаметры
        diameter_start, diameter_end = self._parse_diameters(text)
        if diameter_start:
            parsed.diameter_start = diameter_start
            parsed.parsed_fields.append('diameter_start')
        if diameter_end:
            parsed.diameter_end = diameter_end
            parsed.parsed_fields.append('diameter_end')
        
        # 5. Длина
        parsed.length = self._parse_length(text_lower)
        if parsed.length:
            parsed.parsed_fields.append('length')
        
        # 6. Станок
        parsed.machine_type = self._parse_machine_type(text_lower)
        if parsed.machine_type:
            parsed.parsed_fields.append('machine_type')
        
        # 7. Мощность станка
        parsed.machine_power = self._parse_power(text_lower)
        if parsed.machine_power:
            parsed.parsed_fields.append('machine_power')
        
        # 8. Инструмент
        parsed.tool_material = self._parse_tool_material(text_lower)
        if parsed.tool_material:
            parsed.parsed_fields.append('tool_material')
        
        # 9. Радиус инструмента
        parsed.tool_radius = self._parse_tool_radius(text_lower)
        if parsed.tool_radius:
            parsed.parsed_fields.append('tool_radius')
        
        # 10. Вылет инструмента
        parsed.tool_overhang = self._parse_tool_overhang(text_lower)
        if parsed.tool_overhang:
            parsed.parsed_fields.append('tool_overhang')
        
        # 10.1. Диаметр инструмента (державки/фрезы)
        parsed.tool_diameter = self._parse_tool_diameter(text_lower)
        if parsed.tool_diameter:
            parsed.parsed_fields.append('tool_diameter')
        
        # 10.5. Название инструмента (ISO код)
        parsed.tool_name = self._parse_tool_name(text)
        if parsed.tool_name:
            parsed.parsed_fields.append('tool_name')
        
        # 10.6. Производитель инструмента
        parsed.tool_manufacturer = self._parse_tool_manufacturer(text)
        if parsed.tool_manufacturer:
            parsed.parsed_fields.append('tool_manufacturer')
        
        # 10.7. Марка/градация инструмента
        parsed.tool_grade = self._parse_tool_grade(text)
        if parsed.tool_grade:
            parsed.parsed_fields.append('tool_grade')
        
        # 11. Числовые параметры режимов
        parsed.vc = self._parse_vc(text_lower)
        if parsed.vc:
            parsed.parsed_fields.append('vc')
        
        parsed.rpm = self._parse_rpm(text_lower)
        if parsed.rpm:
            parsed.parsed_fields.append('rpm')
        
        parsed.feed = self._parse_feed(text_lower)
        if parsed.feed:
            parsed.parsed_fields.append('feed')
        
        parsed.ap = self._parse_ap(text_lower)
        if parsed.ap:
            parsed.parsed_fields.append('ap')
        
        # 12. Размер резьбы (M6, M12, M16 и т.д.)
        parsed.thread_size = self._parse_thread_size(text)
        if parsed.thread_size:
            parsed.parsed_fields.append('thread_size')
        
        # 13. Количество деталей
        parsed.quantity = self._parse_quantity(text_lower)
        if parsed.quantity:
            parsed.parsed_fields.append('quantity')
        
        # Рассчитываем уверенность парсинга
        parsed.confidence = len(parsed.parsed_fields) / 17.0  # Максимум 17 полей
        
        return parsed
    
    def _parse_material(self, text: str) -> Optional[str]:
        """Парсить материал."""
        # Сначала проверяем известные материалы
        for material, keywords in self.MATERIAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return material
        
        # Марка с пробелом: "30 хгса" → 30ХГСА (раньше общих 4-значных чисел)
        match = self.MATERIAL_STEEL_GRADE_SPACE.search(text)
        if match:
            num, letters = match.group(1), match.group(2).upper()
            return f"{num}Х{letters}"

        # ГОСТ (Россия): Ст3, 40Х, 30ХГСА, 12Х18Н10Т, Д16Т, ВТ6
        # GB/T, ASTM, EN/DIN марки
        material_patterns = [
            r'\b(Ст\d{1,3})\b',
            r'\b(\d{1,2}[Хх][А-Яа-я]{2,10})\b',  # 30ХГСА, 12ХГСА без пробела
            r'\b(\d{1,2}[Хх]\d{1,2}[А-Яа-я]{0,5})\b',  # 40Х, 12Х18Н10Т
            r'\b([А-Яа-я]{1,3}\d{1,3}[А-Яа-я]{0,3})\b',  # Д16Т, ВТ6, АМг6
            r'\b(GB\s*\d+|GB/T\s*\d+)\b',
            r'\b(\d{4}[A-Z]?)\b',  # 6061, 7075, 2024
            r'\b(AISI\s*\d+|SAE\s*\d+|ASTM\s*\d+)\b',
            r'\b(Ti-[\dA-Z-]+|Grade\s*\d+)\b',
            r'\b([XC]\d+[A-Za-z]+[\d-]+)\b',
            r'\b(EN\s*AW-[\d]+|CW\d+)\b',
            r'\b(\d\.\d{4})\b',
            r'\b([CS]\d+|St\d+)\b',
        ]
        for pattern in material_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                material_name = match.group(1).strip()
                if len(material_name) < 2:
                    continue
                # Не считать материалом 4 цифры подряд, если это не известная марка
                if re.fullmatch(r'\d{4}[A-Z]?', material_name) and material_name[:4] not in self.VALID_4DIGIT_GRADES:
                    continue
                if re.fullmatch(r'\d{4}', material_name) and material_name not in self.VALID_4DIGIT_GRADES:
                    continue
                return material_name

        return None
    
    def _parse_operation(self, text: str) -> Optional[str]:
        """Парсить операцию."""
        for operation, keywords in self.OPERATION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return operation
        return None
    
    def _parse_mode(self, text: str) -> Optional[str]:
        """Парсить режим обработки."""
        for mode, keywords in self.MODE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return mode
        return None
    
    def _parse_diameters(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """Парсить диаметры."""
        # Паттерны: Ø100→Ø90, Ø100 до Ø90, 100-90, 100→90
        patterns = [
            r'[ØDd]?\s*(\d+(?:[.,]\d+)?)\s*(?:до|→|-|–)\s*[ØDd]?\s*(\d+(?:[.,]\d+)?)',
            r'диаметр\s*(\d+(?:[.,]\d+)?)\s*(?:до|→|-|–)\s*(\d+(?:[.,]\d+)?)',
            r'с\s*[ØDd]?\s*(\d+(?:[.,]\d+)?)\s*до\s*[ØDd]?\s*(\d+(?:[.,]\d+)?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    start = float(match.group(1).replace(',', '.'))
                    end = float(match.group(2).replace(',', '.'))
                    return start, end
                except (ValueError, IndexError):
                    continue
        
        # Один диаметр
        single_pattern = r'[ØDd]?\s*(\d+(?:[.,]\d+)?)\s*мм'
        match = re.search(single_pattern, text, re.IGNORECASE)
        if match:
            try:
                diameter = float(match.group(1).replace(',', '.'))
                return diameter, None
            except (ValueError, IndexError):
                pass
        
        return None, None
    
    def _parse_thread_size(self, text: str) -> Optional[str]:
        """
        Парсить размер резьбы (M6, M12, M16 и т.д.).
        
        Улучшенный парсер: распознает "м6", "м 6", "M6", "М12" и т.д.
        """
        # Паттерны: M6, м6, М12, м 12, M 16, м6, м 6
        patterns = [
            r'\b[MМм]\s*(\d+(?:[.,]\d+)?)\b',  # M6, М12, м 16, м6, м 6 (универсальный паттерн)
            r'\bрезьб[аы]\s*[MМм]?\s*(\d+(?:[.,]\d+)?)\b',  # резьба M6, резьба 12
            r'\b[MМм]\s*(\d+(?:[.,]\d+)?)\s*[xх×]\s*\d+',  # M6x30, М12×50
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                thread_num = match.group(1).replace(',', '.')
                try:
                    # Проверяем что это разумный размер резьбы (M3-M100)
                    thread_float = float(thread_num)
                    if 3 <= thread_float <= 100:
                        return f"M{int(thread_float)}"
                except ValueError:
                    continue
        
        return None
    
    def _parse_quantity(self, text: str) -> Optional[int]:
        """
        Парсить количество деталей.
        
        Улучшенный парсер: распознает "кол 50", "кол-во 100", "серия 100 шт" и т.д.
        """
        # Паттерны: серия 100 шт, 100 шт, 100 штук, количество 50, кол 50, кол-во 100
        patterns = [
            r'серия\s+(\d+)\s*(?:шт|штук|штуки)',
            r'(\d+)\s*(?:шт|штук|штуки)',
            r'количество\s+(\d+)',
            r'(\d+)\s*(?:шт|штук|штуки)\s+серия',
            r'\bкол[-\s]?(?:во|вость)?\s*(\d+)\b',  # кол 50, кол-во 100, количество 50 (покрывает все варианты)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    quantity = int(match.group(1))
                    if quantity > 0:
                        return quantity
                except ValueError:
                    continue
        
        return None
    
    def _parse_length(self, text: str) -> Optional[float]:
        """
        Парсить длину.
        
        Улучшенный парсер: распознает "длина 20", "дл 30", "l=50" и т.д.
        """
        patterns = [
            r'длин[аойы]\s*(\d+(?:[.,]\d+)?)',  # длина 20, длиной 30
            r'l\s*[=:]\s*(\d+(?:[.,]\d+)?)',  # l=50, l: 30
            r'(\d+(?:[.,]\d+)?)\s*мм\s*длин',  # 20 мм длин
            r'\bдл[.\s]*(\d+(?:[.,]\d+)?)\b',  # дл 20, дл. 30 (короткая форма)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_machine_type(self, text: str) -> Optional[str]:
        """Парсить тип станка или название станка."""
        """
        Парсить тип станка.
        
        ВАЖНО: НЕ распознает стандарты (ГОСТ/ОСТ/DIN/ISO) как станки.
        """
        text_lower = text.lower()
        
        # КРИТИЧЕСКОЕ ПРАВИЛО: Если есть ГОСТ/ОСТ/DIN/ISO - это НЕ станок
        if re.search(r'\b(гост|ост|din|iso)\s+\d+', text_lower, re.IGNORECASE):
            return None  # Это стандарт, не станок
        
        # Проверяем наличие ключевых слов станка (включая опечатку "чпе" вместо "чпу")
        has_machine_keyword = any(
            keyword in text_lower 
            for keyword in ['станок', 'чпу', 'чпе', 'cnc', 'обрабатывающий центр', 'токарн', 'фрезер', 'машина']
        )
        
        # Если нет ключевых слов станка, но текст похож на название станка (буквы + цифры)
        # Например: "Gamma 1250", "NEF500", "16К20"
        if not has_machine_keyword:
            # Паттерны для названий станков без ключевых слов
            simple_machine_patterns = [
                r'^([А-Яа-яA-Z]{2,}\s*\d{2,}[А-Яа-яA-Z0-9\s]*)$',  # "Gamma 1250", "NEF500"
                r'^([А-Яа-яA-Z]{1,2}\d{2,}[А-Яа-яA-Z0-9]*)$',  # "16К20", "Гамма1250"
                r'^([А-Яа-яA-Za-z]{3,}\s+\d{3,})$',  # "Haas 1000", "DMG 500"
            ]
            for pattern in simple_machine_patterns:
                match = re.match(pattern, text.strip(), re.IGNORECASE)
                if match:
                    machine_name = match.group(1).strip()
                    # Проверяем, что это не просто число и не слишком короткое
                    if len(machine_name) >= 3 and not machine_name.isdigit():
                        return machine_name
            return None
        
        # Сначала проверяем известные типы
        for machine_type, keywords in self.MACHINE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Если нашли известный тип, но есть еще название станка - извлекаем его
                    # Паттерны для названий станков после типа
                    name_patterns = [
                        r'(?:на|станок|машина)\s+([А-Яа-яA-Za-z0-9\s]{3,}?)(?:\s|$|,|\.|\?)',
                        r'([А-Яа-яA-Za-z]{2,}\s*\d+\s*[А-Яа-яA-Za-z]*)\s*(?:станок|машина|токарн|фрезер|tc|cnc)?',
                    ]
                    for pattern in name_patterns:
                        name_match = re.search(pattern, text, re.IGNORECASE)
                        if name_match:
                            machine_name = name_match.group(1).strip()
                            if len(machine_name) > 2:
                                return machine_name
                    return machine_type
        
        # Если не нашли известный тип, ищем паттерны неизвестных станков
        # Паттерны: "работаю на...", "станок...", названия моделей
        machine_patterns = [
            r'станок\s+([А-Яа-яA-Za-z0-9\s]{3,}?)(?:\s|$|,|\.|\?)',  # "станок NEF500", "станок Gamma 1250"
            r'работаю\s+на\s+([А-Яа-яA-Za-z0-9\s]{3,}?)(?:\s|$|,|\.|\?)',  # "работаю на Gamma 1250 tc"
            r'на\s+([А-Яа-яA-Za-z0-9\s]{3,}?)\s+(?:работаю|станок)',  # "на Gamma 1250 работаю"
            r'\b([А-Яа-яA-Z]{2,}\d{2,}[А-Яа-яA-Z0-9]*)\b',  # "NEF500", "16К20", "Гамма1250"
            r'([А-Яа-яA-Za-z]{2,}\s*\d+\s*[А-Яа-яA-Za-z]*)',  # "Gamma 1250 tc"
            r'([А-Яа-яA-Za-z]+\s*\d{3,})',  # "Гамма 1250", "Haas 1000"
        ]
        
        for pattern in machine_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                machine_name = match.group(1).strip()
                # Проверяем, что это не просто число или известное слово
                if len(machine_name) >= 3 and not machine_name.isdigit():
                    # Убираем лишние пробелы и нормализуем
                    machine_name = ' '.join(machine_name.split())
                    # Возвращаем как неизвестный станок (будет сохранен в БД)
                    return machine_name
        
        return None
    
    def _parse_power(self, text: str) -> Optional[float]:
        """Парсить мощность станка."""
        patterns = [
            r'(\d+(?:[.,]\d+)?)\s*(?:квт|kw|киловатт)',
            r'мощност[ьи]\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*квт'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_tool_material(self, text: str) -> Optional[str]:
        """Парсить материал инструмента."""
        for tool_material, keywords in self.TOOL_MATERIAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return tool_material
        return None
    
    def _parse_tool_radius(self, text: str) -> Optional[float]:
        """Парсить радиус инструмента."""
        patterns = [
            r'радиус\s*(?:пластин[ыы]|инструмент[аа]|r)\s*[=:]?\s*(\d+(?:[.,]\d+)?)',
            r'r\s*[=:]?\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*мм\s*радиус'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_tool_overhang(self, text: str) -> Optional[float]:
        """Парсить вылет инструмента."""
        patterns = [
            r'вылет\s*(\d+(?:[.,]\d+)?)',
            r'overhang\s*[=:]?\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*мм\s*вылет'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_tool_diameter(self, text: str) -> Optional[float]:
        """Парсить диаметр инструмента (державки/фрезы)."""
        patterns = [
            r'фреза\s+(\d+(?:[.,]\d+)?)',  # фреза 10, фреза 12.5
            r'фреза\s+[Dd]\s*[=:]\s*(\d+(?:[.,]\d+)?)',  # фреза D=10
            r'[Dd]\s*[=:]\s*(\d+(?:[.,]\d+)?)\s*мм',  # D=12 мм
            r'диаметр\s+инструмента\s+(\d+(?:[.,]\d+)?)',  # диаметр инструмента 16
            r'диаметр\s+фрезы\s+(\d+(?:[.,]\d+)?)',  # диаметр фрезы 20
            r'диаметр\s+державки\s+(\d+(?:[.,]\d+)?)',  # диаметр державки 25
            r'державка\s+(\d+(?:[.,]\d+)?)',  # державка 20
            r'[ØDd]\s*(\d+(?:[.,]\d+)?)\s*мм\s*(?:фрезы|инструмента|державки)',  # Ø10 мм фрезы
            r'(\d+(?:[.,]\d+)?)\s*мм\s*(?:фрезы|инструмента|державки)',  # 10 мм фрезы
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_tool_name(self, text: str) -> Optional[str]:
        """Парсить название инструмента (ISO код)."""
        import re
        text_upper = text.upper()
        
        # Паттерны для ISO кодов: CNMG 120408, WNMG 080408, CNMG120408 и т.д.
        patterns = [
            r'\b(CNMG|WNMG|TNMG|DNMG|VNMG|SNMG|CCMG|DCMG|VCMG|SCMG|VBMT|TBMT|CBMT|TPGN|TPGR|TPGW|APMT|APKT|APGT)\s*(\d{6}|\d{4})\b',
            r'\b(CNMG|WNMG|TNMG|DNMG|VNMG|SNMG|CCMG|DCMG|VCMG|SCMG|VBMT|TBMT|CBMT|TPGN|TPGR|TPGW|APMT|APKT|APGT)\s*(\d{2})\s*(\d{2})\s*(\d{2})\b',
            r'\b(CNMG|WNMG|TNMG|DNMG|VNMG|SNMG|CCMG|DCMG|VCMG|SCMG|VBMT|TBMT|CBMT|TPGN|TPGR|TPGW|APMT|APKT|APGT)\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                # Возвращаем полное название с номером если есть
                if len(match.groups()) > 1 and match.group(2):
                    return f"{match.group(1)} {match.group(2)}"
                return match.group(1)
        
        return None
    
    def _parse_tool_manufacturer(self, text: str) -> Optional[str]:
        """Парсить производителя инструмента."""
        text_upper = text.upper()
        
        for manufacturer in self.TOOL_MANUFACTURERS:
            if manufacturer in text_upper:
                return manufacturer
        
        return None
    
    def _parse_tool_grade(self, text: str) -> Optional[str]:
        """Парсить марку/градацию инструмента."""
        import re
        text_upper = text.upper()
        
        # Паттерны для марок: P25, M15, K10, GC1020, YBC251 и т.д.
        patterns = [
            r'\b([A-Z]\d{2,3}[A-Z]?)\b',  # P25, M15, GC1020
            r'\b([A-Z]{2,3}\d{3,4})\b',   # YBC251, GC1020
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text_upper)
            for match in matches:
                # Исключаем ISO коды инструментов
                if match not in self.ISO_TOOL_CODES:
                    return match
        
        return None
    
    def _parse_vc(self, text: str) -> Optional[float]:
        """Парсить скорость резания."""
        patterns = [
            r'vc\s*[=:]\s*(\d+(?:[.,]\d+)?)',
            r'скорост[ьи]\s*резания\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*(?:м\s*в\s*минуту|м/мин|м\.мин)',
            r'(\d+(?:[.,]\d+)?)\s*м/мин'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_rpm(self, text: str) -> Optional[float]:
        """Парсить обороты."""
        patterns = [
            r'rpm\s*[=:]\s*(\d+(?:[.,]\d+)?)',
            r'оборот[ыа]?\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*(?:об|оборот|rpm)',
            r'n\s*[=:]\s*(\d+(?:[.,]\d+)?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_feed(self, text: str) -> Optional[float]:
        """Парсить подачу."""
        patterns = [
            r'feed\s*[=:]\s*(\d+(?:[.,]\d+)?)',
            r'подач[аиу]\s*(\d+(?:[.,]\d+)?)',
            r'f\s*[=:]\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*мм/об'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_ap(self, text: str) -> Optional[float]:
        """Парсить глубину резания."""
        patterns = [
            r'ap\s*[=:]\s*(\d+(?:[.,]\d+)?)',
            r'глубин[ау]\s*резания\s*(\d+(?:[.,]\d+)?)',
            r'глуб[=:]\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*мм\s*глубин'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except (ValueError, IndexError):
                    continue
        
        return None
