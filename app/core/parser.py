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
    tool_name: Optional[str] = None  # Название инструмента (CNMG, WNMG и т.д.)
    tool_manufacturer: Optional[str] = None  # Производитель
    tool_grade: Optional[str] = None  # Марка/градация
    
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
        'медь': ['медь', 'copper', 'cu']
    }
    
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
        
        # Рассчитываем уверенность парсинга
        parsed.confidence = len(parsed.parsed_fields) / 15.0  # Максимум 15 полей
        
        return parsed
    
    def _parse_material(self, text: str) -> Optional[str]:
        """Парсить материал."""
        # Сначала проверяем известные материалы
        for material, keywords in self.MATERIAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return material
        
        # Если не нашли известный материал, ищем паттерны марок сталей и сплавов
        # Паттерны: марки сталей (40Х, 30ХГСА, Ст45), сплавы (Д16Т, ВТ6)
        material_patterns = [
            r'\b([А-Яа-я]{1,3}\d{1,3}[А-Яа-я]{0,3})\b',  # Марки сталей: 40Х, 30ХГСА, Ст45
            r'\b([А-Яа-я]{1,2}\d{1,3}[А-Яа-я]{0,2})\b',  # Сплавы: Д16Т, ВТ6
            r'\b(Ст\d{1,3})\b',  # Сталь Ст3, Ст45
            r'\b(\d{1,2}Х\d{1,2}[А-Яа-я]{0,5})\b',  # Легированные стали: 40Х, 30ХГСА
        ]
        
        for pattern in material_patterns:
            match = re.search(pattern, text)
            if match:
                material_name = match.group(1).strip()
                # Проверяем, что это похоже на марку материала
                if len(material_name) >= 2:
                    # Возвращаем как неизвестный материал (будет сохранен в БД)
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
    
    def _parse_length(self, text: str) -> Optional[float]:
        """Парсить длину."""
        patterns = [
            r'длин[аойы]\s*(\d+(?:[.,]\d+)?)',
            r'l\s*[=:]\s*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*мм\s*длин'
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
        """Парсить тип станка."""
        # Сначала проверяем известные типы
        for machine_type, keywords in self.MACHINE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
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
            r'работаю\s+на\s+([А-Яа-яA-Za-z0-9\s]{3,}?)(?:\s|$|,|\.|\?)',  # "работаю на Gamma 1250 tc"
            r'станок\s+([А-Яа-яA-Za-z0-9\s]{3,}?)(?:\s|$|,|\.|\?)',  # "станок Gamma 1250"
            r'на\s+([А-Яа-яA-Za-z0-9\s]{3,}?)\s+(?:работаю|станок)',  # "на Gamma 1250 работаю"
            r'([А-Яа-яA-Za-z]{2,}\s*\d+\s*[А-Яа-яA-Za-z]*)',  # "Gamma 1250 tc", "16К20"
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
