"""
ПАРСЕР ИЗОБРАЖЕНИЙ - распознавание инструментов с фотографий.
Использует OCR для извлечения текста с этикеток и маркировок инструментов.
С поддержкой ресайза, многоязычности, QR-кодов и кэширования.
"""

import logging
import os
import hashlib
import pickle
import re
import io
from typing import Dict, Any, Optional, List, Union, BinaryIO
from pathlib import Path
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageOps
    OCR_AVAILABLE = True
    # Задаём путь до проверки (на Windows Tesseract часто не в PATH)
    _tesseract_cmd = os.getenv("TESSERACT_CMD") or os.getenv("TESSERACT_PATH")
    if not _tesseract_cmd and os.name == "nt":
        _win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.isfile(_win):
            _tesseract_cmd = _win
    if _tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd
    # Проверяем доступность Tesseract
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

# OpenCV для продвинутой предобработки (опционально)
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.debug("OpenCV not available. Advanced preprocessing will be limited.")

# QR-коды и штрихкоды (опционально)
try:
    from pyzbar.pyzbar import decode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    decode = None
    logger.debug("QR code libraries not available. Install: pip install pyzbar")


# ============================================================================
# КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ============================================================================

class ImageSource(Enum):
    """Тип источника изображения."""
    BYTES = "bytes"
    FILE = "file"
    URL = "url"
    PIL_IMAGE = "pil_image"


@dataclass
class ImageParserConfig:
    """Конфигурация парсера изображений."""
    MAX_IMAGE_SIZE: int = 2000  # Максимальный размер изображения для ресайза
    CACHE_TTL_SECONDS: int = 3600  # TTL кэша в секундах
    CACHE_DIR: str = "cache/ocr"  # Директория для кэша
    DEFAULT_LANGS: str = "eng+rus"  # Языки по умолчанию
    USE_ADVANCED_PREPROCESSING: bool = True  # Использовать продвинутую предобработку
    USE_ORIENTATION_CORRECTION: bool = True  # Корректировать ориентацию
    USE_QR_SCANNING: bool = True  # Сканировать QR-коды


# ============================================================================
# МЕНЕДЖЕР ЯЗЫКОВ OCR
# ============================================================================

class OCRLanguageManager:
    """Менеджер языков для OCR."""
    
    # Доступные языки Tesseract
    AVAILABLE_LANGS = {
        'eng': 'English',
        'rus': 'Russian',
        'deu': 'German',
        'jpn': 'Japanese',
        'chi_sim': 'Chinese (simplified)',
        'fra': 'French',
        'ita': 'Italian',
        'spa': 'Spanish',
    }
    
    # Типичные языки для производителей
    MANUFACTURER_LANGS: Dict[str, List[str]] = {
        'SANDVIK': ['eng', 'swe'],
        'KENNAMETAL': ['eng'],
        'ISCAR': ['eng', 'heb'],
        'SECO': ['eng', 'fra'],
        'WALTER': ['eng', 'deu'],
        'MITSUBISHI': ['eng', 'jpn'],
        'KYOCERA': ['eng', 'jpn'],
        'TAEGUTEC': ['eng'],
        'KORLOY': ['eng'],
        'SUMITOMO': ['eng', 'jpn'],
    }
    
    # Расширенный список производителей с вариантами написания
    MANUFACTURERS: Dict[str, List[str]] = {
        'SANDVIK': ['SANDVIK', 'SANDVIK COROMANT', 'COROMANT'],
        'KENNAMETAL': ['KENNAMETAL', 'KENNA'],
        'ISCAR': ['ISCAR', 'ISCA'],
        'SECO': ['SECO', 'SECO TOOLS'],
        'WALTER': ['WALTER', 'WALTER TOOLS'],
        'KYOCERA': ['KYOCERA'],
        'MITSUBISHI': ['MITSUBISHI', 'MITSUBISHI MATERIALS'],
        'TAEGUTEC': ['TAEGUTEC'],
        'KORLOY': ['KORLOY'],
        'SUMITOMO': ['SUMITOMO', 'SUMITOMO ELECTRIC'],
    }
    
    @classmethod
    def get_langs_for_image(cls, detected_manufacturer: Optional[str] = None) -> str:
        """
        Определить, какие языки использовать для OCR.
        
        Args:
            detected_manufacturer: Распознанный производитель (если есть)
            
        Returns:
            Строка языков для Tesseract (например, 'eng+rus+deu')
        """
        # Всегда используем английский как базовый
        base_langs = ['eng']
        
        # Если знаем производителя, добавляем его языки
        if detected_manufacturer and detected_manufacturer.upper() in cls.MANUFACTURER_LANGS:
            base_langs.extend(cls.MANUFACTURER_LANGS[detected_manufacturer.upper()])
        
        # Добавляем русский для постсоветского пространства
        if 'rus' not in base_langs:
            base_langs.append('rus')
        
        # Убираем дубликаты и фильтруем доступные языки
        available = [lang for lang in base_langs if lang in cls.AVAILABLE_LANGS]
        
        return '+'.join(available) if available else 'eng'


# ============================================================================
# ПАРСЕР ISO КОДОВ
# ============================================================================

class ISOCodeParser:
    """Парсер ISO кодов пластин."""
    
    # Структура ISO кода: C N M G 12 04 08
    # Позиции: 1-форма, 2-задний угол, 3-допуски, 4-тип, 5-длина, 6-толщина, 7-радиус
    
    SHAPE_MAP = {
        'C': 'ромбическая 80°',
        'W': 'треугольная 60°',
        'T': 'треугольная 60°',
        'D': 'ромбическая 55°',
        'V': 'ромбическая 35°',
        'S': 'квадратная 90°',
        'R': 'круглая',
        'A': 'параллелограмм 85°',
        'B': 'параллелограмм 82°',
        'K': 'параллелограмм 55°',
    }
    
    CLEARANCE_ANGLE_MAP = {
        'N': '0°',
        'A': '3°',
        'B': '5°',
        'C': '7°',
        'D': '15°',
        'E': '20°',
        'F': '25°',
        'G': '30°',
    }
    
    TOLERANCE_MAP = {
        'M': 'средние допуски (шлифованные)',
        'G': 'шлифованная',
        'U': 'нешлифованная',
    }
    
    @classmethod
    def parse(cls, iso_code: str) -> Dict[str, Any]:
        """
        Разобрать ISO код пластины.
        
        Args:
            iso_code: ISO код (например, CNMG120408)
            
        Returns:
            Словарь с разобранными данными
        """
        if len(iso_code) < 4:
            return {}
        
        result = {
            'full_code': iso_code,
            'shape': cls.SHAPE_MAP.get(iso_code[0], 'неизвестно'),
            'clearance_angle': cls.CLEARANCE_ANGLE_MAP.get(iso_code[1], 'неизвестно'),
            'tolerance': cls.TOLERANCE_MAP.get(iso_code[2], 'неизвестно'),
        }
        
        # Длина режущей кромки (позиции 5-6)
        if len(iso_code) >= 6:
            try:
                length_code = iso_code[4:6]
                if length_code.isdigit():
                    result['cutting_edge_length'] = int(length_code)  # в мм
            except Exception:
                pass
        
        # Толщина пластины (позиции 7-8)
        if len(iso_code) >= 8:
            try:
                thickness_code = iso_code[6:8]
                if thickness_code.isdigit():
                    result['insert_thickness'] = int(thickness_code) / 10.0  # в мм
            except Exception:
                pass
        
        # Радиус при вершине (позиция 9-10)
        if len(iso_code) >= 10:
            radius = cls._parse_radius_from_iso(iso_code)
            if radius:
                result['insert_radius'] = radius
        
        return result
    
    @classmethod
    def _parse_radius_from_iso(cls, iso_code: str) -> Optional[float]:
        """
        Парсить радиус из ISO кода с учетом контекста.
        В ISO: последние две цифры - радиус в десятых долях мм.
        """
        try:
            if len(iso_code) >= 10:
                radius_code = iso_code[8:10]
                if radius_code.isdigit():
                    radius_mm = int(radius_code) / 10.0
                    
                    # Валидация разумных значений
                    if 0.1 <= radius_mm <= 3.2:
                        return radius_mm
                    else:
                        logger.warning(f"Unusual radius value: {radius_mm}mm from code {radius_code}")
        except Exception:
            pass
        
        return None


# ============================================================================
# КЭШИРОВАНИЕ OCR
# ============================================================================

class OCRCache:
    """Кэш для результатов OCR."""
    
    def __init__(self, cache_dir: str = "cache/ocr"):
        """
        Инициализация кэша.
        
        Args:
            cache_dir: Директория для кэша
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_image_hash(self, image_data: bytes) -> str:
        """Получить хеш изображения."""
        return hashlib.md5(image_data).hexdigest()
    
    def get(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Получить результат из кэша.
        
        Args:
            image_data: Байты изображения
            
        Returns:
            Результат из кэша или None
        """
        # Проверяем memory cache
        image_hash = self._get_image_hash(image_data)
        if image_hash in self.memory_cache:
            return self.memory_cache[image_hash]
        
        # Проверяем disk cache
        cache_file = self.cache_dir / f"{image_hash}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    result = pickle.load(f)
                self.memory_cache[image_hash] = result
                return result
            except Exception as e:
                logger.debug(f"Failed to load cache: {e}")
        
        return None
    
    def set(self, image_data: bytes, result: Dict[str, Any]):
        """
        Сохранить результат в кэш.
        
        Args:
            image_data: Байты изображения
            result: Результат OCR
        """
        image_hash = self._get_image_hash(image_data)
        self.memory_cache[image_hash] = result
        
        cache_file = self.cache_dir / f"{image_hash}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
        except Exception as e:
            logger.warning(f"Failed to cache OCR result: {e}")
    
    def clear(self):
        """Очистить кэш."""
        self.memory_cache.clear()


# ============================================================================
# ОСНОВНОЙ КЛАСС ПАРСЕРА
# ============================================================================

class ImageParser:
    """
    Парсер изображений для распознавания инструментов.
    Использует OCR для извлечения текста с фотографий.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None, config: Optional[ImageParserConfig] = None):
        """
        Инициализация парсера изображений.
        
        Args:
            tesseract_cmd: Путь к исполняемому файлу Tesseract (опционально)
            config: Конфигурация парсера
        """
        self.config = config or ImageParserConfig()
        self.cache = OCRCache(cache_dir=self.config.CACHE_DIR)
        
        # Изначально проверяем доступность через системный PATH
        self.ocr_available = OCR_AVAILABLE and TESSERACT_AVAILABLE
        
        # Настройка пути к Tesseract если указан
        if OCR_AVAILABLE and tesseract_cmd:
            try:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
                pytesseract.get_tesseract_version()
                self.ocr_available = True
                logger.info(f"✅ Tesseract OCR configured from .env: {tesseract_cmd}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to configure Tesseract path {tesseract_cmd}: {e}")
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
    
    def _resize_if_needed(self, image: Image.Image, max_size: int = None) -> Image.Image:
        """
        Уменьшить изображение, если оно слишком большое.
        Tesseract лучше работает с изображениями 300dpi, но не с гигантскими размерами.
        
        Args:
            image: Изображение PIL
            max_size: Максимальный размер (если None, используется из конфига)
            
        Returns:
            Изображение (возможно уменьшенное)
        """
        max_size = max_size or self.config.MAX_IMAGE_SIZE
        width, height = image.size
        
        if width > max_size or height > max_size:
            # Сохраняем пропорции
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.debug(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        
        return image
    
    def _correct_orientation(self, image: Image.Image) -> Image.Image:
        """
        Определить и исправить ориентацию изображения.
        Использует Tesseract для определения перевернутых страниц.
        
        Args:
            image: Изображение PIL
            
        Returns:
            Изображение с исправленной ориентацией
        """
        if not self.config.USE_ORIENTATION_CORRECTION or not self.ocr_available:
            return image
        
        try:
            # Пробуем определить ориентацию
            osd = pytesseract.image_to_osd(image)
            
            # Парсим результат
            angle_match = re.search(r'Rotate: (\d+)', osd)
            if angle_match:
                angle = int(angle_match.group(1))
                if angle != 0:
                    image = image.rotate(-angle, expand=True)  # Отрицательный угол для поворота обратно
                    logger.info(f"Corrected image orientation by {angle} degrees")
        
        except Exception as e:
            logger.debug(f"Orientation detection failed: {e}")
        
        return image
    
    def _scan_qr_code(self, image: Image.Image) -> Optional[Dict[str, Any]]:
        """
        Сканировать QR-код или штрихкод на изображении.
        
        Args:
            image: Изображение PIL
            
        Returns:
            Данные из QR-кода или None
        """
        if not self.config.USE_QR_SCANNING or not QR_AVAILABLE:
            return None
        
        try:
            # Декодируем все штрихкоды
            decoded_objects = decode(image)
            
            for obj in decoded_objects:
                data = obj.data.decode('utf-8')
                qr_type = obj.type  # QRCODE, EAN13, etc.
                
                # Парсим данные QR-кода
                if qr_type == 'QRCODE':
                    # Может быть JSON или просто строка
                    if data.startswith('{') and data.endswith('}'):
                        try:
                            import json
                            return json.loads(data)
                        except:
                            pass
                    
                    # Простая строка - возможно ISO код
                    return {
                        'tool_name': data,
                        'source': 'qr_code',
                        'confidence': 1.0
                    }
        
        except Exception as e:
            logger.debug(f"QR code scanning failed: {e}")
        
        return None
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Предобработка изображения для улучшения OCR.
        Для светлого текста на тёмном фоне (державки, маркировка) — инвертируем.
        
        Args:
            image: Изображение PIL
            
        Returns:
            Предобработанное изображение
        """
        # Сначала уменьшаем если нужно
        image = self._resize_if_needed(image)
        
        # Корректируем ориентацию
        image = self._correct_orientation(image)
        
        # Используем продвинутую предобработку если доступна
        if self.config.USE_ADVANCED_PREPROCESSING and OPENCV_AVAILABLE:
            try:
                return self._advanced_preprocess(image)
            except Exception as e:
                logger.debug(f"Advanced preprocessing failed, using basic: {e}")
        
        # Базовая предобработка
        return self._basic_preprocess(image)
    
    def _basic_preprocess(self, image: Image.Image) -> Image.Image:
        """Базовая предобработка изображения."""
        # Конвертируем в RGB если нужно
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Проверяем среднюю яркость — если изображение тёмное, инвертируем
        gray = image.convert('L')
        mean_brightness = sum(gray.getdata()) / (gray.size[0] * gray.size[1])
        if mean_brightness < 140:
            image = ImageOps.invert(image)
        
        # Увеличиваем контраст
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Увеличиваем резкость
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        return image
    
    def _advanced_preprocess(self, image: Image.Image) -> Image.Image:
        """
        Продвинутая предобработка изображения с использованием OpenCV.
        
        Args:
            image: Изображение PIL
            
        Returns:
            Предобработанное изображение
        """
        if not OPENCV_AVAILABLE:
            return self._basic_preprocess(image)
        
        try:
            # Конвертируем PIL в OpenCV
            img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # 1. Удаление шума
            img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
            
            # 2. Конвертация в градации серого
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 3. Адаптивная бинаризация (лучше чем простая инверсия)
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # 4. Морфологические операции для улучшения текста
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel)
            
            # Конвертируем обратно в PIL
            return Image.fromarray(morph)
        
        except Exception as e:
            logger.debug(f"Advanced preprocessing error: {e}")
            return self._basic_preprocess(image)
    
    def get_text_from_image(self, image_data: bytes) -> str:
        """
        Извлечь сырой текст с изображения через OCR.
        
        Args:
            image_data: Байты изображения
            
        Returns:
            Текст, распознанный с изображения, или пустая строка при ошибке
        """
        if not self.ocr_available:
            return ""
        
        try:
            image = Image.open(io.BytesIO(image_data))
            image = self._preprocess_image(image)
            return pytesseract.image_to_string(image, lang=self.config.DEFAULT_LANGS)
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
        # Проверяем кэш
        cached_result = self.cache.get(image_data)
        if cached_result:
            logger.debug("Using cached OCR result")
            return cached_result
        
        if not self.ocr_available:
            result = {
                'success': False,
                'error': 'OCR not available. Install pytesseract and pillow.',
                'tool_name': None,
                'extracted_text': None
            }
            self.cache.set(image_data, result)
            return result
        
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))
            
            # Сначала пробуем сканировать QR-код
            qr_result = self._scan_qr_code(image)
            if qr_result:
                logger.info("Found QR code on image")
                result = {
                    'success': True,
                    'tool_name': qr_result.get('tool_name'),
                    'source': 'qr_code',
                    'confidence': qr_result.get('confidence', 1.0),
                    'extracted_text': None
                }
                self.cache.set(image_data, result)
                return result
            
            # Предобработка изображения для лучшего OCR
            processed_image = self._preprocess_image(image)
            
            # Извлекаем текст
            try:
                # Определяем производителя для выбора языков
                detected_manufacturer = None
                temp_text = pytesseract.image_to_string(processed_image, lang='eng')
                for manufacturer, variants in OCRLanguageManager.MANUFACTURERS.items():
                    for variant in variants:
                        if variant in temp_text.upper():
                            detected_manufacturer = manufacturer
                            break
                    if detected_manufacturer:
                        break
                
                # Используем подходящие языки
                langs = OCRLanguageManager.get_langs_for_image(detected_manufacturer)
                extracted_text = pytesseract.image_to_string(processed_image, lang=langs)
            
            except pytesseract.pytesseract.TesseractNotFoundError:
                logger.warning("Tesseract OCR engine not found. Cannot parse image.")
                result = {
                    'success': False,
                    'error': 'Tesseract OCR не установлен. Установите Tesseract OCR для распознавания текста с изображений.',
                    'tool_name': None,
                    'extracted_text': None
                }
                self.cache.set(image_data, result)
                return result
            
            # Парсим текст для поиска информации об инструменте
            tool_info = self._parse_tool_text(extracted_text)
            
            result = {
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
            
            # Сохраняем в кэш
            self.cache.set(image_data, result)
            return result
        
        except Exception as e:
            logger.error(f"Error parsing tool image: {e}", exc_info=True)
            result = {
                'success': False,
                'error': str(e),
                'tool_name': None,
                'extracted_text': None
            }
            self.cache.set(image_data, result)
            return result
    
    async def parse_tool_images_batch(self, images_data: List[bytes]) -> List[Dict[str, Any]]:
        """
        Пакетная обработка нескольких изображений.
        
        Args:
            images_data: Список байтов изображений
            
        Returns:
            Список результатов
        """
        import asyncio
        
        async def process_single(image_data):
            loop = asyncio.get_event_loop()
            # Запускаем в thread pool executor (OCR блокирующая операция)
            return await loop.run_in_executor(
                None, self.parse_tool_image, image_data
            )
        
        tasks = [process_single(img) for img in images_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed = []
        for result in results:
            if isinstance(result, Exception):
                processed.append({
                    'success': False,
                    'error': str(result)
                })
            else:
                processed.append(result)
        
        return processed
    
    async def parse_from_source(
        self,
        source: Union[bytes, str, Path, BinaryIO, Image.Image],
        source_type: Optional[ImageSource] = None
    ) -> Dict[str, Any]:
        """
        Распарсить изображение из разных источников.
        
        Args:
            source: Источник изображения (байты, путь, URL, PIL Image)
            source_type: Тип источника (если None, определяется автоматически)
            
        Returns:
            Результат парсинга
        """
        if source_type is None:
            # Автоопределение типа
            if isinstance(source, bytes):
                source_type = ImageSource.BYTES
            elif isinstance(source, (str, Path)):
                source_type = ImageSource.FILE
            elif isinstance(source, Image.Image):
                source_type = ImageSource.PIL_IMAGE
            else:
                source_type = ImageSource.BYTES
        
        try:
            if source_type == ImageSource.BYTES:
                return self.parse_tool_image(source)
            
            elif source_type == ImageSource.FILE:
                with open(source, 'rb') as f:
                    return self.parse_tool_image(f.read())
            
            elif source_type == ImageSource.URL:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(source) as response:
                        image_data = await response.read()
                        return self.parse_tool_image(image_data)
            
            elif source_type == ImageSource.PIL_IMAGE:
                # Конвертируем PIL в байты
                img_byte_arr = io.BytesIO()
                source.save(img_byte_arr, format='PNG')
                return self.parse_tool_image(img_byte_arr.getvalue())
        
        except Exception as e:
            logger.error(f"Error parsing from {source_type}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _parse_tool_text(self, text: str) -> Dict[str, Any]:
        """
        Парсить текст для извлечения информации об инструменте.
        
        Args:
            text: Текст, извлеченный OCR
            
        Returns:
            Словарь с информацией об инструменте
        """
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
        # 1) Маркировка державок: MGEHR1212-2, PGER2525M16, SDJCR/L 2525 M-16 и т.п.
        holder_patterns = [
            r'\b([A-Z]{2,6}[-]?\d{4,8}(?:[-]\d+)?)\b',   # MGEHR1212-2, PGER2020
            r'\b([A-Z]{2,5}\d{2,4}[A-Z]?\d{0,2}(?:[-]\d+)?)\b',  # SDJCR2525M16
        ]
        for pattern in holder_patterns:
            match = re.search(pattern, text_upper)
            if match:
                candidate = match.group(1)
                # Отсекаем явный мусор (только цифры, слишком короткое)
                if len(candidate) >= 6 and not candidate.isdigit():
                    result['tool_name'] = match.group(1)
                    result['tool_type'] = 'державка/оправка'
                    result['confidence'] = 0.75
                    break
        
        # 2) ISO пластины: CNMG, WNMG, TNMG, DNMG, VNMG и т.д.
        if not result['tool_name']:
            iso_patterns = [
                r'\b(CNMG|WNMG|TNMG|DNMG|VNMG|SNMG|CCMG|DCMG|VCMG|SCMG)\s*(\d{6}|\d{4})\b',
                r'\b(CNMG|WNMG|TNMG|DNMG|VNMG|SNMG|CCMG|DCMG|VCMG|SCMG)\s*(\d{2})\s*(\d{2})\s*(\d{2})\b',
            ]
            for pattern in iso_patterns:
                match = re.search(pattern, text_upper)
                if match:
                    iso_code = match.group(1)
                    result['tool_name'] = match.group(0)
                    result['tool_type'] = self._determine_tool_type(iso_code)
                    result['confidence'] = 0.8
                    
                    # Парсим ISO код для извлечения радиуса
                    if len(match.groups()) > 1:
                        full_iso = match.group(0).replace(' ', '')
                        iso_data = ISOCodeParser.parse(full_iso)
                        if iso_data.get('insert_radius'):
                            result['insert_radius'] = iso_data['insert_radius']
                    break
        
        # Поиск производителей (расширенный список)
        for manufacturer, variants in OCRLanguageManager.MANUFACTURERS.items():
            for variant in variants:
                if variant in text_upper:
                    result['manufacturer'] = manufacturer
                    break
            if result['manufacturer']:
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
        # Используем парсер ISO кодов
        iso_data = ISOCodeParser.parse(iso_code)
        shape = iso_data.get('shape', 'неизвестная форма')
        
        # Вторая буква определяет тип
        if 'N' in iso_code or 'M' in iso_code:
            return f'токарный проходной ({shape})'
        else:
            return f'токарный инструмент ({shape})'
