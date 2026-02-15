"""
Умный браузерный парсер для поиска информации об инструментах, станках и операциях.

Решает проблемы:
- SPA (Sandvik, Kennametal, Iscar, Seco, Walter): Playwright выполняет JS.
- Реальная асинхронность: aiohttp вместо requests + run_in_executor.
- Поиск по сайтам: у каждого сайта свой способ (форма поиска через Playwright).
- Контекстное извлечение: мощность шпинделя, а не насоса/освещения (секции + целевые regex).
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import quote_plus

from app.knowledge.internet_parser.site_config import (
    get_tool_sites,
    get_machine_sites,
    SiteConfig,
)
from app.knowledge.internet_parser.context_extractor import (
    extract_tool_data_context_aware,
    extract_machine_data_context_aware,
    extract_operation_data_context_aware,
)

logger = logging.getLogger(__name__)

try:
    from app.knowledge.internet_parser.fetch_aiohttp import fetch_html_aiohttp, AIOHTTP_AVAILABLE
except ImportError:
    AIOHTTP_AVAILABLE = False
    fetch_html_aiohttp = None

try:
    from app.knowledge.internet_parser.fetch_playwright import (
        fetch_via_playwright_search,
        fetch_url_playwright,
        PLAYWRIGHT_AVAILABLE,
    )
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    fetch_via_playwright_search = None
    fetch_url_playwright = None


async def _fetch_for_site(site: SiteConfig, query: str) -> Optional[str]:
    """
    Загрузить контент для одного сайта: либо через Playwright (SPA), либо aiohttp (URL GET).
    """
    if site.needs_js and PLAYWRIGHT_AVAILABLE and site.search_input_selector:
        return await fetch_via_playwright_search(
            base_url=site.base_url,
            query=query,
            search_input_selector=site.search_input_selector,
            search_submit_selector=site.search_submit_selector,
            results_container_selector=site.results_container_selector,
            wait_after_sec=site.wait_after_search_sec,
        )
    if site.search_url_template and AIOHTTP_AVAILABLE:
        url = site.search_url_template.format(query=quote_plus(query))
        return await fetch_html_aiohttp(url, extra_headers=site.extra_headers)
    return None


async def _fetch_one_site(site: SiteConfig, query: str) -> Tuple[SiteConfig, Optional[str]]:
    """Загрузить один сайт; вернуть (config, html)."""
    try:
        html = await _fetch_for_site(site, query)
        return (site, html)
    except Exception as e:
        logger.debug(f"Fetch failed {site.id}: {e}")
        return (site, None)


async def _fetch_all_sites(sites: List[SiteConfig], query: str) -> List[Tuple[SiteConfig, Optional[str]]]:
    """Параллельно загрузить все сайты (реальная async-параллельность)."""
    tasks = [_fetch_one_site(site, query) for site in sites]
    return await asyncio.gather(*tasks, return_exceptions=False)


class BrowserParser:
    """
    Умный парсер: aiohttp + Playwright (SPA), посайтовая конфигурация, контекстное извлечение.
    """

    def __init__(self):
        """Инициализация: проверка доступности бэкендов."""
        self._aiohttp_ok = AIOHTTP_AVAILABLE
        self._playwright_ok = PLAYWRIGHT_AVAILABLE
        if not self._aiohttp_ok:
            logger.warning("aiohttp not available. Install: pip install aiohttp")
        if not self._playwright_ok:
            logger.warning(
                "Playwright not available for SPA sites. "
                "Install: pip install -r requirements_internet.txt && playwright install"
            )

    async def search_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Поиск информации об инструменте.
        Параллельный опрос сайтов; для SPA — Playwright (поиск по форме).
        Извлечение — контекстное (радиус/материал/mark/VC из нужных секций).
        """
        result: Dict[str, Any] = {
            "success": False,
            "tool_name": tool_name,
            "found_data": {},
            "sources": [],
        }
        if not self._aiohttp_ok and not self._playwright_ok:
            result["error"] = "Neither aiohttp nor Playwright available"
            return result

        sites = get_tool_sites(use_playwright=self._playwright_ok)
        if not sites:
            return result

        try:
            results = await _fetch_all_sites(sites, tool_name)
            for site, html in results:
                if not html:
                    continue
                extracted = extract_tool_data_context_aware(html, tool_name)
                if extracted:
                    result["found_data"].update(extracted)
                    result["sources"].append(site.base_url)
                    result["success"] = True
        except Exception as e:
            logger.error(f"Error searching tool info: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    async def search_machine_info(self, machine_name: str) -> Dict[str, Any]:
        """
        Поиск информации о станке.
        Мощность и обороты извлекаются только из контекста шпинделя/привода.
        """
        result: Dict[str, Any] = {
            "success": False,
            "machine_name": machine_name,
            "found_data": {},
            "sources": [],
        }
        if not self._aiohttp_ok and not self._playwright_ok:
            result["error"] = "Neither aiohttp nor Playwright available"
            return result

        sites = get_machine_sites(use_playwright=self._playwright_ok)
        if not sites:
            return result

        try:
            results = await _fetch_all_sites(sites, machine_name)
            for site, html in results:
                if not html:
                    continue
                extracted = extract_machine_data_context_aware(html, machine_name)
                if extracted:
                    result["found_data"].update(extracted)
                    result["sources"].append(site.base_url)
                    result["success"] = True
        except Exception as e:
            logger.error(f"Error searching machine info: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    async def search_operation_info(
        self, operation_type: str, material: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Поиск режимов резания для типа операции (и опционально материала).
        Контекстное извлечение vc_min/vc_max из секций про скорость резания.
        """
        result: Dict[str, Any] = {
            "success": False,
            "operation_type": operation_type,
            "material": material,
            "found_data": {},
            "sources": [],
        }
        if not self._aiohttp_ok and not self._playwright_ok:
            result["error"] = "Neither aiohttp nor Playwright available"
            return result

        query = f"{operation_type} режимы резания"
        if material:
            query += f" {material}"

        # Используем те же сайты инструментов — там есть разделы по режимам
        sites = get_tool_sites(use_playwright=self._playwright_ok)
        if not sites:
            return result

        try:
            results = await _fetch_all_sites(sites, query)
            for site, html in results:
                if not html:
                    continue
                extracted = extract_operation_data_context_aware(
                    html, operation_type, material or ""
                )
                if extracted:
                    result["found_data"].update(extracted)
                    result["sources"].append(site.base_url)
                    result["success"] = True
        except Exception as e:
            logger.error(f"Error searching operation info: {e}", exc_info=True)
            result["error"] = str(e)

        return result
