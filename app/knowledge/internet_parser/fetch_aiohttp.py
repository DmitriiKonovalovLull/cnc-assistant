"""
Асинхронная загрузка страниц через aiohttp.
Реальная async-параллельность без блокировки пула потоков.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None


DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5) if aiohttp else None
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}


async def fetch_html_aiohttp(url: str, extra_headers: Optional[dict] = None) -> Optional[str]:
    """
    Загрузить HTML по URL асинхронно (aiohttp).
    
    Args:
        url: URL страницы
        extra_headers: Дополнительные заголовки
        
    Returns:
        Текст страницы или None при ошибке
    """
    if not AIOHTTP_AVAILABLE:
        logger.warning("aiohttp not available")
        return None
    headers = {**DEFAULT_HEADERS}
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT, headers=headers) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.text()
    except Exception as e:
        logger.debug(f"aiohttp fetch failed {url}: {e}")
        return None
