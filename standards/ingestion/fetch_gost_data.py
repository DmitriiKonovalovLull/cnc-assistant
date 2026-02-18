"""
Загрузка актуальных данных ГОСТ и ISO из открытых источников.
Скачивает таблицы резьб, допусков, посадок и сохраняет в JSON.
Fallback на встроенные базовые данные при отсутствии интернета.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# Путь к директории данных
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Файлы для сохранения
GOST_THREADS_FILE = DATA_DIR / "gost_threads_actual.json"
ISO_TOLERANCES_FILE = DATA_DIR / "iso_tolerances_actual.json"

# User-Agent для запросов (имитация браузера)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Заголовки для запросов
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Базовые данные для fallback (если нет интернета)
FALLBACK_GOST_THREADS = {
    "source": "fallback",
    "threads": [
        {"diameter": 1.0, "pitch": 0.25, "coarse": True},
        {"diameter": 1.2, "pitch": 0.25, "coarse": True},
        {"diameter": 1.4, "pitch": 0.3, "coarse": True},
        {"diameter": 1.6, "pitch": 0.35, "coarse": True},
        {"diameter": 2.0, "pitch": 0.4, "coarse": True},
        {"diameter": 2.5, "pitch": 0.45, "coarse": True},
        {"diameter": 3.0, "pitch": 0.5, "coarse": True},
        {"diameter": 4.0, "pitch": 0.7, "coarse": True},
        {"diameter": 5.0, "pitch": 0.8, "coarse": True},
        {"diameter": 6.0, "pitch": 1.0, "coarse": True},
        {"diameter": 8.0, "pitch": 1.25, "coarse": True},
        {"diameter": 10.0, "pitch": 1.5, "coarse": True},
        {"diameter": 12.0, "pitch": 1.75, "coarse": True},
        {"diameter": 16.0, "pitch": 2.0, "coarse": True},
        {"diameter": 20.0, "pitch": 2.5, "coarse": True},
        {"diameter": 24.0, "pitch": 3.0, "coarse": True},
        {"diameter": 30.0, "pitch": 3.5, "coarse": True},
        {"diameter": 36.0, "pitch": 4.0, "coarse": True},
        {"diameter": 42.0, "pitch": 4.5, "coarse": True},
        {"diameter": 48.0, "pitch": 5.0, "coarse": True},
        {"diameter": 56.0, "pitch": 5.5, "coarse": True},
        {"diameter": 64.0, "pitch": 6.0, "coarse": True},
    ],
}

FALLBACK_ISO_TOLERANCES = {
    "source": "fallback",
    "tolerances": {
        # Примерные значения допусков в мкм для диапазонов размеров (IT6-IT11)
        "IT6": {"3-6": 6, "6-10": 7, "10-18": 9, "18-30": 11, "30-50": 13, "50-80": 16, "80-120": 19},
        "IT7": {"3-6": 10, "6-10": 12, "10-18": 15, "18-30": 18, "30-50": 21, "50-80": 25, "80-120": 30},
        "IT8": {"3-6": 14, "6-10": 18, "10-18": 22, "18-30": 27, "30-50": 33, "50-80": 39, "80-120": 46},
        "IT9": {"3-6": 25, "6-10": 30, "10-18": 36, "18-30": 43, "30-50": 52, "50-80": 62, "80-120": 74},
        "IT10": {"3-6": 40, "6-10": 48, "10-18": 58, "18-30": 70, "30-50": 84, "50-80": 100, "80-120": 120},
        "IT11": {"3-6": 60, "6-10": 75, "10-18": 90, "18-30": 110, "30-50": 130, "50-80": 160, "80-120": 190},
    },
}


def _fetch_url_sync(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Синхронная загрузка URL через requests."""
    try:
        import requests
        response = requests.get(url, headers=headers or DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except ImportError:
        logger.warning("requests library not available, cannot fetch online data")
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def _parse_html_table(html: str) -> List[List[str]]:
    """Простой парсер HTML таблиц (без BeautifulSoup)."""
    if not html:
        return []
    # Ищем <table>...</table>
    table_pattern = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL | re.IGNORECASE)
    tables = table_pattern.findall(html)
    if not tables:
        return []
    # Берем первую таблицу
    table_html = tables[0]
    # Ищем строки <tr>...</tr>
    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    rows = row_pattern.findall(table_html)
    parsed_rows = []
    for row in rows:
        # Ищем ячейки <td>...</td> или <th>...</th>
        cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
        cells = cell_pattern.findall(row)
        # Очищаем HTML теги из ячеек
        cleaned_cells = []
        for cell in cells:
            # Убираем все теги
            cleaned = re.sub(r"<[^>]+>", "", cell)
            # Нормализуем пробелы
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            cleaned_cells.append(cleaned)
        if cleaned_cells:
            parsed_rows.append(cleaned_cells)
    return parsed_rows


def _parse_thread_table(rows: List[List[str]]) -> List[Dict[str, Any]]:
    """Парсинг таблицы резьб: ищем диаметр и шаг."""
    threads = []
    for row in rows:
        if len(row) < 2:
            continue
        # Ищем числа (диаметр и шаг)
        numbers = []
        for cell in row:
            # Извлекаем числа (целые и с десятичной точкой/запятой)
            nums = re.findall(r"\d+(?:[.,]\d+)?", cell.replace(",", "."))
            for num_str in nums:
                try:
                    num = float(num_str)
                    if 0.1 <= num <= 200:  # Разумный диапазон для резьб
                        numbers.append(num)
                except ValueError:
                    continue
        if len(numbers) >= 2:
            # Первое число - диаметр, второе - шаг
            diameter = numbers[0]
            pitch = numbers[1]
            threads.append({
                "diameter": diameter,
                "pitch": pitch,
                "coarse": True,  # По умолчанию крупный шаг
            })
    return threads


def fetch_gost_threads() -> Dict[str, Any]:
    """
    Скачивает актуальные данные ГОСТ по резьбам из открытых источников.
    Возвращает словарь с ключом 'threads' (список резьб).
    При ошибке сети использует fallback данные.
    """
    # Источники данных (можно добавить несколько)
    sources = [
        "https://docs.cntd.ru/document/1200000001",  # Пример URL (нужно уточнить реальный)
        # Можно добавить зеркала или альтернативные источники
    ]
    
    all_threads = []
    
    for source_url in sources:
        try:
            logger.info(f"Fetching GOST threads from {source_url}")
            html = _fetch_url_sync(source_url)
            if not html:
                continue
            
            # Парсим таблицы
            tables = _parse_html_table(html)
            for table in tables:
                threads = _parse_thread_table(table)
                all_threads.extend(threads)
            
            if all_threads:
                logger.info(f"Parsed {len(all_threads)} threads from {source_url}")
                break  # Успешно загрузили, выходим
        except Exception as e:
            logger.warning(f"Error fetching from {source_url}: {e}")
            continue
    
    # Если ничего не загрузили, используем fallback
    if not all_threads:
        logger.info("Using fallback GOST threads data")
        result = FALLBACK_GOST_THREADS.copy()
    else:
        result = {
            "source": "online",
            "threads": all_threads,
        }
    
    # Сохраняем в файл
    try:
        with open(GOST_THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved GOST threads to {GOST_THREADS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save GOST threads: {e}")
    
    return result


def _parse_tolerance_table(rows: List[List[str]]) -> Dict[str, Dict[str, float]]:
    """Парсинг таблицы допусков ISO 286."""
    tolerances = {}
    current_grade = None
    
    for row in rows:
        if not row:
            continue
        # Ищем заголовок с IT (IT6, IT7, ...)
        grade_match = None
        for cell in row:
            grade_match = re.search(r"IT\s*(\d+)", cell, re.IGNORECASE)
            if grade_match:
                current_grade = f"IT{grade_match.group(1)}"
                tolerances[current_grade] = {}
                break
        
        if current_grade and len(row) >= 3:
            # Пытаемся извлечь диапазон размеров и значение допуска
            numbers = []
            for cell in row:
                nums = re.findall(r"\d+(?:[.,]\d+)?", cell.replace(",", "."))
                for num_str in nums:
                    try:
                        num = float(num_str)
                        if 0.1 <= num <= 10000:  # Разумный диапазон
                            numbers.append(num)
                    except ValueError:
                        continue
            
            if len(numbers) >= 2:
                # Первое число - начало диапазона, второе - конец, третье - допуск
                size_start = numbers[0]
                size_end = numbers[1] if len(numbers) > 1 else size_start + 10
                tolerance_value = numbers[2] if len(numbers) > 2 else numbers[1]
                
                range_key = f"{size_start}-{size_end}"
                tolerances[current_grade][range_key] = tolerance_value
    
    return tolerances


def fetch_iso_tolerances() -> Dict[str, Any]:
    """
    Скачивает данные ISO 286 (допуски и посадки) из открытых технических библиотек.
    Извлекает значения допусков для квалитетов IT01-IT18.
    Возвращает словарь с ключом 'tolerances'.
    При ошибке сети использует fallback данные.
    """
    # Источники данных
    sources = [
        "https://www.iso.org/standard/21450.html",  # ISO 286 (нужно уточнить реальный URL с таблицами)
        # Можно добавить альтернативные источники
    ]
    
    all_tolerances = {}
    
    for source_url in sources:
        try:
            logger.info(f"Fetching ISO tolerances from {source_url}")
            html = _fetch_url_sync(source_url)
            if not html:
                continue
            
            # Парсим таблицы
            tables = _parse_html_table(html)
            for table in tables:
                tolerances = _parse_tolerance_table(table)
                # Объединяем с уже найденными
                for grade, values in tolerances.items():
                    if grade not in all_tolerances:
                        all_tolerances[grade] = {}
                    all_tolerances[grade].update(values)
            
            if all_tolerances:
                logger.info(f"Parsed tolerances for grades: {list(all_tolerances.keys())}")
                break
        except Exception as e:
            logger.warning(f"Error fetching from {source_url}: {e}")
            continue
    
    # Если ничего не загрузили, используем fallback
    if not all_tolerances:
        logger.info("Using fallback ISO tolerances data")
        result = FALLBACK_ISO_TOLERANCES.copy()
    else:
        result = {
            "source": "online",
            "tolerances": all_tolerances,
        }
    
    # Сохраняем в файл
    try:
        with open(ISO_TOLERANCES_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved ISO tolerances to {ISO_TOLERANCES_FILE}")
    except Exception as e:
        logger.error(f"Failed to save ISO tolerances: {e}")
    
    return result


def update_all_data() -> Dict[str, Any]:
    """
    Запускает оба парсера: fetch_gost_threads и fetch_iso_tolerances.
    Возвращает словарь с результатами обоих обновлений.
    """
    logger.info("Starting data update: GOST threads and ISO tolerances")
    
    results = {
        "gost_threads": None,
        "iso_tolerances": None,
        "errors": [],
    }
    
    try:
        results["gost_threads"] = fetch_gost_threads()
    except Exception as e:
        error_msg = f"Error fetching GOST threads: {e}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
    
    try:
        results["iso_tolerances"] = fetch_iso_tolerances()
    except Exception as e:
        error_msg = f"Error fetching ISO tolerances: {e}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
    
    logger.info("Data update completed")
    return results


def load_gost_threads() -> Dict[str, Any]:
    """Загрузить сохраненные данные ГОСТ резьб из файла или fallback."""
    if GOST_THREADS_FILE.exists():
        try:
            with open(GOST_THREADS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load GOST threads from file: {e}")
    return FALLBACK_GOST_THREADS.copy()


def load_iso_tolerances() -> Dict[str, Any]:
    """Загрузить сохраненные данные ISO допусков из файла или fallback."""
    if ISO_TOLERANCES_FILE.exists():
        try:
            with open(ISO_TOLERANCES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load ISO tolerances from file: {e}")
    return FALLBACK_ISO_TOLERANCES.copy()


if __name__ == "__main__":
    # Тестовый запуск
    logging.basicConfig(level=logging.INFO)
    results = update_all_data()
    print(f"GOST threads: {len(results.get('gost_threads', {}).get('threads', []))} entries")
    print(f"ISO tolerances: {len(results.get('iso_tolerances', {}).get('tolerances', {}))} grades")
    if results.get("errors"):
        print(f"Errors: {results['errors']}")
