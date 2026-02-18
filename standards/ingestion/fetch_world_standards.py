"""
Загрузка стандартов всех стран из открытых источников.
Параллельная загрузка через asyncio для всех мировых систем стандартов.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Путь к директории данных
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# User-Agent для запросов (имитация браузера)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Заголовки для запросов
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6,ja;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


async def _fetch_url_async(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Optional[str]:
    """Асинхронная загрузка URL через aiohttp."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers or DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                response.raise_for_status()
                return await response.text()
    except ImportError:
        logger.warning("aiohttp not available, falling back to requests")
        return _fetch_url_sync(url, headers)
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def _fetch_url_sync(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Синхронная загрузка URL через requests (fallback)."""
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


def _save_metadata(source: str, metadata: Dict[str, Any]) -> None:
    """Сохранить метаданные о загрузке."""
    metadata_file = DATA_DIR / source / "metadata.json"
    metadata_file.parent.mkdir(exist_ok=True)
    try:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save metadata for {source}: {e}")


async def fetch_gost_data() -> Dict[str, Any]:
    """
    Загрузить данные ГОСТ РФ из открытых источников.
    Источники: docs.cntd.ru, protect.gost.ru
    Сохраняет в data/gost/
    """
    source = "gost"
    sources = [
        "https://docs.cntd.ru/document/1200000001",  # Пример URL (нужно уточнить реальный)
        "https://protect.gost.ru/",  # Портал стандартов
    ]
    
    result = {
        "source": source,
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "urls_tried": sources,
        "data_files": [],
        "errors": [],
    }
    
    gost_dir = DATA_DIR / source
    gost_dir.mkdir(exist_ok=True)
    
    for url in sources:
        try:
            logger.info(f"Fetching GOST data from {url}")
            html = await _fetch_url_async(url)
            if html:
                # Сохраняем сырой HTML для дальнейшей обработки
                html_file = gost_dir / f"raw_{url.split('/')[-1] or 'index'}.html"
                try:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    result["data_files"].append(str(html_file.name))
                    result["success"] = True
                    logger.info(f"Saved GOST data from {url} to {html_file}")
                except Exception as e:
                    result["errors"].append(f"Failed to save {url}: {e}")
        except Exception as e:
            error_msg = f"Error fetching GOST from {url}: {e}"
            logger.warning(error_msg)
            result["errors"].append(error_msg)
    
    _save_metadata(source, result)
    return result


async def fetch_iso_data() -> Dict[str, Any]:
    """
    Загрузить данные ISO из открытых источников.
    Источники: iso.org, standards.iso.org
    Сохраняет в data/iso/
    """
    source = "iso"
    sources = [
        "https://www.iso.org/standard/21450.html",  # ISO 286 (пример)
        "https://standards.iso.org/",  # Портал стандартов ISO
    ]
    
    result = {
        "source": source,
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "urls_tried": sources,
        "data_files": [],
        "errors": [],
    }
    
    iso_dir = DATA_DIR / source
    iso_dir.mkdir(exist_ok=True)
    
    for url in sources:
        try:
            logger.info(f"Fetching ISO data from {url}")
            html = await _fetch_url_async(url)
            if html:
                html_file = iso_dir / f"raw_{url.split('/')[-1] or 'index'}.html"
                try:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    result["data_files"].append(str(html_file.name))
                    result["success"] = True
                    logger.info(f"Saved ISO data from {url} to {html_file}")
                except Exception as e:
                    result["errors"].append(f"Failed to save {url}: {e}")
        except Exception as e:
            error_msg = f"Error fetching ISO from {url}: {e}"
            logger.warning(error_msg)
            result["errors"].append(error_msg)
    
    _save_metadata(source, result)
    return result


async def fetch_din_data() -> Dict[str, Any]:
    """
    Загрузить данные DIN (Германия) из открытых источников.
    Источники: beuth.de, din.de
    Сохраняет в data/din/
    """
    source = "din"
    sources = [
        "https://www.beuth.de/",  # Beuth Verlag (издатель стандартов DIN)
        "https://www.din.de/",  # Официальный сайт DIN
    ]
    
    result = {
        "source": source,
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "urls_tried": sources,
        "data_files": [],
        "errors": [],
    }
    
    din_dir = DATA_DIR / source
    din_dir.mkdir(exist_ok=True)
    
    for url in sources:
        try:
            logger.info(f"Fetching DIN data from {url}")
            html = await _fetch_url_async(url)
            if html:
                html_file = din_dir / f"raw_{url.split('/')[-2] or 'index'}.html"
                try:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    result["data_files"].append(str(html_file.name))
                    result["success"] = True
                    logger.info(f"Saved DIN data from {url} to {html_file}")
                except Exception as e:
                    result["errors"].append(f"Failed to save {url}: {e}")
        except Exception as e:
            error_msg = f"Error fetching DIN from {url}: {e}"
            logger.warning(error_msg)
            result["errors"].append(error_msg)
    
    _save_metadata(source, result)
    return result


async def fetch_gb_data() -> Dict[str, Any]:
    """
    Загрузить данные GB (Китай) из открытых источников.
    Источники: gbstandards.org, chinesestandard.net
    Важно: китайские стандарты часто = ISO + модификации
    Сохраняет в data/gb/
    """
    source = "gb"
    sources = [
        "http://www.gbstandards.org/",  # Портал стандартов GB
        "https://www.chinesestandard.net/",  # Китайские стандарты
    ]
    
    result = {
        "source": source,
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "urls_tried": sources,
        "data_files": [],
        "errors": [],
        "note": "Chinese standards often = ISO + modifications",
    }
    
    gb_dir = DATA_DIR / source
    gb_dir.mkdir(exist_ok=True)
    
    for url in sources:
        try:
            logger.info(f"Fetching GB data from {url}")
            html = await _fetch_url_async(url)
            if html:
                html_file = gb_dir / f"raw_{url.split('/')[-2] or 'index'}.html"
                try:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    result["data_files"].append(str(html_file.name))
                    result["success"] = True
                    logger.info(f"Saved GB data from {url} to {html_file}")
                except Exception as e:
                    result["errors"].append(f"Failed to save {url}: {e}")
        except Exception as e:
            error_msg = f"Error fetching GB from {url}: {e}"
            logger.warning(error_msg)
            result["errors"].append(error_msg)
    
    _save_metadata(source, result)
    return result


async def fetch_jis_data() -> Dict[str, Any]:
    """
    Загрузить данные JIS (Япония) из открытых источников.
    Источники: jisc.go.jp
    Сохраняет в data/jis/
    """
    source = "jis"
    sources = [
        "https://www.jisc.go.jp/",  # Japanese Industrial Standards Committee
    ]
    
    result = {
        "source": source,
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "urls_tried": sources,
        "data_files": [],
        "errors": [],
    }
    
    jis_dir = DATA_DIR / source
    jis_dir.mkdir(exist_ok=True)
    
    for url in sources:
        try:
            logger.info(f"Fetching JIS data from {url}")
            html = await _fetch_url_async(url)
            if html:
                html_file = jis_dir / f"raw_{url.split('/')[-2] or 'index'}.html"
                try:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    result["data_files"].append(str(html_file.name))
                    result["success"] = True
                    logger.info(f"Saved JIS data from {url} to {html_file}")
                except Exception as e:
                    result["errors"].append(f"Failed to save {url}: {e}")
        except Exception as e:
            error_msg = f"Error fetching JIS from {url}: {e}"
            logger.warning(error_msg)
            result["errors"].append(error_msg)
    
    _save_metadata(source, result)
    return result


async def fetch_ansi_data() -> Dict[str, Any]:
    """
    Загрузить данные ANSI (США) из открытых источников.
    Источники: ansi.org
    Сохраняет в data/ansi/
    """
    source = "ansi"
    sources = [
        "https://www.ansi.org/",  # American National Standards Institute
    ]
    
    result = {
        "source": source,
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "urls_tried": sources,
        "data_files": [],
        "errors": [],
    }
    
    ansi_dir = DATA_DIR / source
    ansi_dir.mkdir(exist_ok=True)
    
    for url in sources:
        try:
            logger.info(f"Fetching ANSI data from {url}")
            html = await _fetch_url_async(url)
            if html:
                html_file = ansi_dir / f"raw_{url.split('/')[-2] or 'index'}.html"
                try:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    result["data_files"].append(str(html_file.name))
                    result["success"] = True
                    logger.info(f"Saved ANSI data from {url} to {html_file}")
                except Exception as e:
                    result["errors"].append(f"Failed to save {url}: {e}")
        except Exception as e:
            error_msg = f"Error fetching ANSI from {url}: {e}"
            logger.warning(error_msg)
            result["errors"].append(error_msg)
    
    _save_metadata(source, result)
    return result


async def fetch_bs_data() -> Dict[str, Any]:
    """
    Загрузить данные BS (Британия) из открытых источников.
    Источники: bsigroup.com
    Сохраняет в data/bs/
    """
    source = "bs"
    sources = [
        "https://www.bsigroup.com/",  # BSI Group (British Standards Institution)
    ]
    
    result = {
        "source": source,
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "urls_tried": sources,
        "data_files": [],
        "errors": [],
    }
    
    bs_dir = DATA_DIR / source
    bs_dir.mkdir(exist_ok=True)
    
    for url in sources:
        try:
            logger.info(f"Fetching BS data from {url}")
            html = await _fetch_url_async(url)
            if html:
                html_file = bs_dir / f"raw_{url.split('/')[-2] or 'index'}.html"
                try:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                    result["data_files"].append(str(html_file.name))
                    result["success"] = True
                    logger.info(f"Saved BS data from {url} to {html_file}")
                except Exception as e:
                    result["errors"].append(f"Failed to save {url}: {e}")
        except Exception as e:
            error_msg = f"Error fetching BS from {url}: {e}"
            logger.warning(error_msg)
            result["errors"].append(error_msg)
    
    _save_metadata(source, result)
    return result


async def fetch_all_standards() -> Dict[str, Any]:
    """
    Главная функция: запускает все загрузчики параллельно через asyncio.
    Логирует успехи/неудачи, сохраняет метаданные о каждом источнике.
    
    Returns:
        Словарь с результатами всех загрузок:
        {
            "timestamp": "...",
            "results": {
                "gost": {...},
                "iso": {...},
                ...
            },
            "summary": {
                "total": 7,
                "successful": 3,
                "failed": 4
            }
        }
    """
    logger.info("Starting parallel fetch of all world standards")
    start_time = datetime.now()
    
    # Запускаем все загрузчики параллельно
    results = await asyncio.gather(
        fetch_gost_data(),
        fetch_iso_data(),
        fetch_din_data(),
        fetch_gb_data(),
        fetch_jis_data(),
        fetch_ansi_data(),
        fetch_bs_data(),
        return_exceptions=True,
    )
    
    # Обрабатываем результаты
    results_dict = {}
    successful = 0
    failed = 0
    
    sources = ["gost", "iso", "din", "gb", "jis", "ansi", "bs"]
    for i, result in enumerate(results):
        source = sources[i] if i < len(sources) else f"unknown_{i}"
        if isinstance(result, Exception):
            logger.error(f"Exception in {source}: {result}")
            results_dict[source] = {
                "source": source,
                "success": False,
                "error": str(result),
                "timestamp": datetime.now().isoformat(),
            }
            failed += 1
        else:
            results_dict[source] = result
            if result.get("success"):
                successful += 1
            else:
                failed += 1
    
    # Формируем итоговый результат
    summary = {
        "timestamp": start_time.isoformat(),
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
        "results": results_dict,
        "summary": {
            "total": len(results),
            "successful": successful,
            "failed": failed,
        },
    }
    
    # Сохраняем общий отчёт
    summary_file = DATA_DIR / "fetch_summary.json"
    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved fetch summary to {summary_file}")
    except Exception as e:
        logger.error(f"Failed to save summary: {e}")
    
    logger.info(f"Fetch completed: {successful} successful, {failed} failed")
    return summary


def fetch_all_standards_sync() -> Dict[str, Any]:
    """
    Синхронная обёртка для fetch_all_standards().
    Используется если asyncio недоступен или для простых скриптов.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(fetch_all_standards())


if __name__ == "__main__":
    # Тестовый запуск
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("Fetching world standards...")
    summary = fetch_all_standards_sync()
    
    print(f"\nSummary:")
    print(f"  Total: {summary['summary']['total']}")
    print(f"  Successful: {summary['summary']['successful']}")
    print(f"  Failed: {summary['summary']['failed']}")
    print(f"  Duration: {summary['summary'].get('duration_seconds', 0):.2f} seconds")
    
    print("\nResults by source:")
    for source, result in summary["results"].items():
        status = "✓" if result.get("success") else "✗"
        print(f"  {status} {source}: {len(result.get('data_files', []))} files")
