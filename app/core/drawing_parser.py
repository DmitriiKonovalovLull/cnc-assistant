"""
ПАРСЕР ЧЕРТЕЖЕЙ - извлечение информации о деталях из чертежей (изображений).
Распознает размеры, допуски, материалы, стандарты из технических чертежей.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass
import io

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR libraries not available. Install: pip install pytesseract pillow opencv-python")


@dataclass
class DrawingData:
    """Результат парсинга чертежа."""
    # Основная информация
    part_name: Optional[str] = None
    part_number: Optional[str] = None
    standard: Optional[str] = None  # ГОСТ, ОСТ, DIN, ISO
    
    # Размеры
    diameters: List[float] = None
    lengths: List[float] = None
    widths: List[float] = None
    heights: List[float] = None
    
    # Допуски и точность
    tolerances: Dict[str, float] = None
    surface_roughness: Optional[str] = None
    
    # Материал
    material: Optional[str] = None
    material_grade: Optional[str] = None
    
    # Операции
    operations: List[str] = None
    
    # Метаданные
    extracted_text: Optional[str] = None
    confidence: float = 0.0
    parsed_fields: List[str] = None
    
    def __post_init__(self):
        if self.diameters is None:
            self.diameters = []
        if self.lengths is None:
            self.lengths = []
        if self.widths is None:
            self.widths = []
        if self.heights is None:
            self.heights = []
        if self.tolerances is None:
            self.tolerances = {}
        if self.operations is None:
            self.operations = []
        if self.parsed_fields is None:
            self.parsed_fields = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            'part_name': self.part_name,
            'part_number': self.part_number,
            'standard': self.standard,
            'diameters': self.diameters,
            'lengths': self.lengths,
            'widths': self.widths,
            'heights': self.heights,
            'tolerances': self.tolerances,
            'surface_roughness': self.surface_roughness,
            'material': self.material,
            'material_grade': self.material_grade,
            'operations': self.operations,
            'extracted_text': self.extracted_text,
            'confidence': self.confidence,
            'parsed_fields': self.parsed_fields
        }


class DrawingParser:
    """
    Парсер чертежей для извлечения информации о деталях.
    Использует OCR и компьютерное зрение для распознавания размеров и параметров.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Инициализация парсера чертежей.
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract (опционально)
        """
        self.ocr_available = OCR_AVAILABLE
        if OCR_AVAILABLE and tesseract_cmd:
            try:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
                pytesseract.get_tesseract_version()
                self.ocr_available = True
                logger.info(f"✅ Tesseract OCR configured: {tesseract_cmd}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to configure Tesseract: {e}")
                self.ocr_available = False
    
    def parse_drawing(self, image_data: bytes) -> DrawingData:
        """
        Распарсить чертеж (изображение).
        
        Args:
            image_data: Байты изображения чертежа
            
        Returns:
            DrawingData с извлеченными данными
        """
        result = DrawingData()
        
        if not self.ocr_available:
            result.confidence = 0.0
            result.extracted_text = "OCR не доступен"
            return result
        
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))
            
            # Предобработка для улучшения OCR
            processed_image = self._preprocess_drawing(image)
            
            # Извлекаем текст с чертежа
            extracted_text = pytesseract.image_to_string(
                processed_image,
                lang='eng+rus',
                config='--psm 6'  # Предполагаем единый блок текста
            )
            
            result.extracted_text = extracted_text
            
            # Парсим текст для извлечения информации
            self._parse_drawing_text(extracted_text, result)
            
            # Пытаемся найти размеры на изображении (компьютерное зрение)
            self._extract_dimensions_from_image(image, result)
            
            # Рассчитываем уверенность
            result.confidence = self._calculate_confidence(result)
            
        except Exception as e:
            logger.error(f"Error parsing drawing: {e}", exc_info=True)
            result.confidence = 0.0
        
        return result
    
    def _preprocess_drawing(self, image: Image.Image) -> Image.Image:
        """
        Предобработка изображения чертежа для улучшения OCR.
        
        Args:
            image: Исходное изображение
            
        Returns:
            Обработанное изображение
        """
        # Конвертируем в RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Конвертируем PIL в OpenCV формат
        img_array = np.array(image)
        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Конвертируем в grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Увеличиваем контраст
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # Бинаризация (черно-белое)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Убираем шум
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Конвертируем обратно в PIL
        processed = Image.fromarray(binary)
        
        return processed
    
    def _parse_drawing_text(self, text: str, result: DrawingData) -> None:
        """
        Парсить текст чертежа для извлечения информации.
        
        Args:
            text: Текст, извлеченный OCR
            result: Объект DrawingData для заполнения
        """
        text_upper = text.upper()
        text_lower = text.lower()
        
        # 1. Название детали
        part_name_patterns = [
            r'наименование[:\s]+([А-Яа-яA-Za-z0-9\s\-]+)',
            r'деталь[:\s]+([А-Яа-яA-Za-z0-9\s\-]+)',
            r'название[:\s]+([А-Яа-яA-Za-z0-9\s\-]+)',
        ]
        for pattern in part_name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.part_name = match.group(1).strip()
                result.parsed_fields.append('part_name')
                break
        
        # 2. Номер детали
        part_number_patterns = [
            r'№[:\s]+([А-Яа-яA-Za-z0-9\-]+)',
            r'номер[:\s]+([А-Яа-яA-Za-z0-9\-]+)',
            r'обозначение[:\s]+([А-Яа-яA-Za-z0-9\-]+)',
        ]
        for pattern in part_number_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.part_number = match.group(1).strip()
                result.parsed_fields.append('part_number')
                break
        
        # 3. Стандарт (ГОСТ, ОСТ, DIN, ISO)
        standard_patterns = [
            r'\b(ГОСТ|ОСТ|DIN|ISO)\s*(\d+(?:[-\s]\d+)?)',
            r'\b(ГОСТ|ОСТ|DIN|ISO)\s*(\d+(?:[-\s]\d+)?)',
        ]
        for pattern in standard_patterns:
            match = re.search(pattern, text_upper, re.IGNORECASE)
            if match:
                standard_type = match.group(1).upper()
                standard_number = match.group(2).strip()
                result.standard = f"{standard_type} {standard_number}"
                result.parsed_fields.append('standard')
                break
        
        # 4. Материал
        material_patterns = [
            r'материал[:\s]+([А-Яа-яA-Za-z0-9\s\-]+)',
            r'материал[:\s]+([А-Яа-я]{1,3}\d{1,3}[А-Яа-я]{0,3})',  # Марки сталей
            r'([А-Яа-я]{1,3}\d{1,3}[А-Яа-я]{0,3})\s+материал',
        ]
        for pattern in material_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                material = match.group(1).strip()
                result.material = material
                result.material_grade = material
                result.parsed_fields.append('material')
                break
        
        # 5. Диаметры (Ø100, D=100, диаметр 100)
        diameter_patterns = [
            r'[ØDd]?\s*(\d+(?:[.,]\d+)?)\s*мм',
            r'диаметр[:\s]+(\d+(?:[.,]\d+)?)',
            r'[ØDd]\s*[=:]\s*(\d+(?:[.,]\d+)?)',
        ]
        for pattern in diameter_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    diameter = float(match.replace(',', '.'))
                    if diameter not in result.diameters:
                        result.diameters.append(diameter)
                        result.parsed_fields.append('diameters')
                except ValueError:
                    continue
        
        # 6. Длины (L=100, длина 100)
        length_patterns = [
            r'[Ll]\s*[=:]\s*(\d+(?:[.,]\d+)?)',
            r'длин[аойы][:\s]+(\d+(?:[.,]\d+)?)',
            r'длин[аойы]\s*(\d+(?:[.,]\d+)?)\s*мм',
        ]
        for pattern in length_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    length = float(match.replace(',', '.'))
                    if length not in result.lengths:
                        result.lengths.append(length)
                        result.parsed_fields.append('lengths')
                except ValueError:
                    continue
        
        # 7. Допуски (IT7, H7, h6, ±0.1)
        tolerance_patterns = [
            r'IT\s*(\d+)',
            r'\b([Hh]\d+|[Ff]\d+|[Gg]\d+)\b',
            r'[±]\s*(\d+(?:[.,]\d+)?)',
            r'допуск[:\s]+([±]?\d+(?:[.,]\d+)?)',
        ]
        for pattern in tolerance_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match not in result.tolerances:
                    result.tolerances[match] = 0.0  # Значение будет уточнено
                    result.parsed_fields.append('tolerances')
        
        # 8. Шероховатость (Ra 1.6, Ra=3.2)
        roughness_patterns = [
            r'Ra\s*[=:]?\s*(\d+(?:[.,]\d+)?)',
            r'шероховатость[:\s]+Ra\s*(\d+(?:[.,]\d+)?)',
        ]
        for pattern in roughness_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.surface_roughness = f"Ra {match.group(1)}"
                result.parsed_fields.append('surface_roughness')
                break
        
        # 9. Операции (токарная, фрезерная)
        operation_keywords = {
            'токарная': ['токар', 'точение', 'обтачивание'],
            'фрезерная': ['фрезер', 'фреза'],
            'сверление': ['сверл', 'отверстие'],
            'растачивание': ['расточ'],
        }
        for operation, keywords in operation_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if operation not in result.operations:
                        result.operations.append(operation)
                        result.parsed_fields.append('operations')
                    break
    
    def _extract_dimensions_from_image(self, image: Image.Image, result: DrawingData) -> None:
        """
        Извлечь размеры с чертежа используя компьютерное зрение.
        
        Args:
            image: Изображение чертежа
            result: Объект DrawingData для заполнения
        """
        if not OCR_AVAILABLE:
            return
        
        try:
            # Конвертируем PIL в OpenCV
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                img_cv = img_array
            
            # Находим линии размеров (размерные линии обычно прямые)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
            
            # Детектор линий
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=50, maxLineGap=10)
            
            # Здесь можно добавить логику для определения размеров по линиям
            # Пока оставляем базовую реализацию
            
        except Exception as e:
            logger.debug(f"Could not extract dimensions from image: {e}")
    
    def _calculate_confidence(self, result: DrawingData) -> float:
        """
        Рассчитать уверенность парсинга.
        
        Args:
            result: Результат парсинга
            
        Returns:
            Уверенность от 0.0 до 1.0
        """
        confidence = 0.0
        
        # Базовые поля
        if result.part_name:
            confidence += 0.15
        if result.part_number:
            confidence += 0.1
        if result.standard:
            confidence += 0.2
        if result.material:
            confidence += 0.15
        
        # Размеры
        if result.diameters:
            confidence += 0.1
        if result.lengths:
            confidence += 0.1
        
        # Допуски и точность
        if result.tolerances:
            confidence += 0.1
        if result.surface_roughness:
            confidence += 0.1
        
        return min(confidence, 1.0)
