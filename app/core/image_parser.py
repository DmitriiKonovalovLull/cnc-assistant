"""
ПАРСЕР ИЗОБРАЖЕНИЙ - распознавание инструментов с фотографий.
Использует OCR для извлечения текста с этикеток и маркировок инструментов.
"""

import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import io

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
    # Задаём путь до проверки (на Windows Tesseract часто не в PATH)
    _tesseract_cmd = os.getenv("TESSERACT_CMD") or os.getenv("TESSERACT_PATH")
    if not _tesseract_cmd and os.name == "nt":
        _win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.isfile(_win):
            _tesseract_cmd = _win
    if _tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd
    # Проверяем доступность Tesseract (или из PATH, или уже заданный путь)
    try:
        pytesseract.get_tesseract_version()
        TESSERACT_AVAILABLE = True
    except Exception:
        TESSERACT_AVAILABLE = False
        logger.warning("Tesseract OCR engine not found. Install Tesseract OCR: https://github.com/tesseract-ocr/tesseract")
except ImportError:
    OCR_AVAILABLE = False
    TESSERACT_AVAILABLE = False
    logger.warning("OCR libraries not available. Install: pip install pytesseract pillow")


class ImageParser:
    """
    Парсер изображений для распознавания инструментов.
    Использует OCR для извлечения текста с фотографий.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Инициализация парсера изображений.
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract (опционально)
        """
        # Изначально проверяем доступность через системный PATH
        self.ocr_available = OCR_AVAILABLE and TESSERACT_AVAILABLE
        
        # Настройка пути к Tesseract если указан (приоритет над системным PATH)
        if OCR_AVAILABLE and tesseract_cmd:
            try:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
                # Проверяем доступность после установки пути
                pytesseract.get_tesseract_version()
                self.ocr_available = True
                logger.info(f"✅ Tesseract OCR configured from .env: {tesseract_cmd}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to configure Tesseract path {tesseract_cmd}: {e}")
                # Пробуем использовать системный PATH если кастомный путь не работает
                if TESSERACT_AVAILABLE:
                    self.ocr_available = True
                    logger.info("Using Tesseract from system PATH instead")
                else:
                    self.ocr_available = False
        
        # Логирование статуса OCR
        if not OCR_AVAILABLE:
            logger.warning("⚠️ OCR libraries not available. Install: pip install pytesseract pillow")
        elif self.ocr_available:
            try:
                version = pytesseract.get_tesseract_version()
                logger.info(f"✅ OCR ready: Tesseract {version}")
            except:
                pass
        else:
            logger.warning("⚠️ Tesseract OCR engine not found. Image parsing will be limited.")
            logger.info("💡 To enable OCR: set TESSERACT_CMD in .env or install Tesseract in PATH")
    
    def get_text_from_image(self, image_data: bytes) -> str:
        """
        Извлечь сырой текст с изображения через OCR (для спектра вибрации, FFT и т.д.).
        Returns:
            Текст, распознанный с изображения, или пустая строка при ошибке.
        """
        if not self.ocr_available:
            return ""
        try:
            image = Image.open(io.BytesIO(image_data))
            image = self._preprocess_image(image)
            return pytesseract.image_to_string(image, lang='eng+rus')
        except Exception as e:
            logger.warning(f"OCR get_text_from_image failed: {e}")
            return ""

    def parse_tool_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        Распарсить изображение инструмента.
        
        Args:
            image_data: Байты изображения
            
        Returns:
            Словарь с извлеченными данными об инструменте
        """
        if not self.ocr_available:
            return {
                'success': False,
                'error': 'OCR not available. Install pytesseract and pillow.',
                'tool_name': None,
                'extracted_text': None
            }
        
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))
            
            # Предобработка изображения для лучшего OCR
            image = self._preprocess_image(image)
            
            # Извлекаем текст
            try:
                extracted_text = pytesseract.image_to_string(image, lang='eng+rus')
            except pytesseract.pytesseract.TesseractNotFoundError:
                logger.warning("Tesseract OCR engine not found. Cannot parse image.")
                return {
                    'success': False,
                    'error': 'Tesseract OCR не установлен. Установите Tesseract OCR для распознавания текста с изображений.',
                    'tool_name': None,
                    'extracted_text': None
                }
            
            # Парсим текст для поиска информации об инструменте
            tool_info = self._parse_tool_text(extracted_text)
            
            return {
                'success': True,
                'tool_name': tool_info.get('tool_name'),
                'tool_type': tool_info.get('tool_type'),
                'insert_material': tool_info.get('insert_material'),
                'insert_grade': tool_info.get('insert_grade'),
                'insert_radius': tool_info.get('insert_radius'),
                'manufacturer': tool_info.get('manufacturer'),
                'extracted_text': extracted_text,
                'confidence': tool_info.get('confidence', 0.5)
            }
        
        except Exception as e:
            logger.error(f"Error parsing tool image: {e}", exc_info=True)
            # Проверяем, это ли ошибка Tesseract
            if 'TesseractNotFoundError' in str(type(e)) or 'tesseract' in str(e).lower():
                return {
                    'success': False,
                    'error': 'Tesseract OCR не установлен. Установите Tesseract OCR для распознавания текста с изображений.',
                    'tool_name': None,
                    'extracted_text': None
                }
            return {
                'success': False,
                'error': str(e),
                'tool_name': None,
                'extracted_text': None
            }
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Предобработка изображения для улучшения OCR.
        
        Args:
            image: Исходное изображение
            
        Returns:
            Обработанное изображение
        """
        # Конвертируем в RGB если нужно
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Увеличиваем контраст
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Увеличиваем резкость
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        return image
    
    def _parse_tool_text(self, text: str) -> Dict[str, Any]:
        """
        Парсить текст для извлечения информации об инструменте.
        
        Args:
            text: Текст, извлеченный OCR
            
        Returns:
            Словарь с информацией об инструменте
        """
        import re
        
        text_upper = text.upper()
        text_lower = text.lower()
        
        result = {
            'tool_name': None,
            'tool_type': None,
            'insert_material': None,
            'insert_grade': None,
            'insert_radius': None,
            'manufacturer': None,
            'confidence': 0.5
        }
        
        # Паттерны для распознавания инструментов
        # ISO стандарты: CNMG, WNMG, TNMG, DNMG, VNMG и т.д.
        iso_patterns = [
            r'\b(CNMG|WNMG|TNMG|DNMG|VNMG|SNMG|CCMG|DCMG|VCMG|SCMG)\s*(\d{6}|\d{4})\b',
            r'\b(CNMG|WNMG|TNMG|DNMG|VNMG|SNMG|CCMG|DCMG|VCMG|SCMG)\s*(\d{2})\s*(\d{2})\s*(\d{2})\b',
        ]
        
        for pattern in iso_patterns:
            match = re.search(pattern, text_upper)
            if match:
                result['tool_name'] = match.group(0)
                result['tool_type'] = self._determine_tool_type(match.group(1))
                result['confidence'] = 0.8
                
                # Пытаемся извлечь радиус из номера
                if len(match.groups()) > 1:
                    numbers = match.groups()[1:]
                    if numbers:
                        # Радиус обычно в формате 08, 12, 16 (0.8, 1.2, 1.6 мм)
                        radius_str = numbers[-1] if len(numbers) > 0 else None
                        if radius_str:
                            try:
                                radius = float(radius_str) / 10.0
                                result['insert_radius'] = radius
                            except:
                                pass
                break
        
        # Поиск производителей
        manufacturers = ['SANDVIK', 'KENNAMETAL', 'ISCAR', 'SECO', 'WALTER', 'KYOCERA', 'MITSUBISHI']
        for manufacturer in manufacturers:
            if manufacturer in text_upper:
                result['manufacturer'] = manufacturer
                break
        
        # Поиск материала/марки
        material_patterns = {
            'carbide': ['CARBIDE', 'WC', 'TUNGSTEN'],
            'ceramic': ['CERAMIC', 'CERAMICS'],
            'cbn': ['CBN', 'CUBIC BORON NITRIDE'],
            'diamond': ['DIAMOND', 'PCD']
        }
        
        for material, keywords in material_patterns.items():
            for keyword in keywords:
                if keyword in text_upper:
                    result['insert_material'] = material
                    break
            if result['insert_material']:
                break
        
        # Поиск марки/градации
        grade_pattern = r'\b([A-Z]\d{2,3}[A-Z]?)\b'
        grade_match = re.search(grade_pattern, text_upper)
        if grade_match:
            result['insert_grade'] = grade_match.group(1)
        
        # Если нашли хотя бы название инструмента, повышаем уверенность
        if result['tool_name']:
            result['confidence'] = 0.7
            if result['manufacturer']:
                result['confidence'] = 0.85
            if result['insert_material']:
                result['confidence'] = 0.9
        
        return result
    
    def _determine_tool_type(self, iso_code: str) -> str:
        """
        Определить тип инструмента по ISO коду.
        
        Args:
            iso_code: ISO код инструмента (CNMG, WNMG и т.д.)
            
        Returns:
            Тип инструмента
        """
        # Первая буква определяет форму
        shape_map = {
            'C': 'ромбическая 80°',
            'W': 'треугольная 60°',
            'T': 'треугольная',
            'D': 'ромбическая 55°',
            'V': 'ромбическая 35°',
            'S': 'квадратная'
        }
        
        shape = shape_map.get(iso_code[0], 'неизвестная форма')
        
        # Вторая буква определяет тип
        if 'N' in iso_code:
            return f'токарный проходной ({shape})'
        elif 'M' in iso_code:
            return f'токарный проходной ({shape})'
        else:
            return f'токарный инструмент ({shape})'
