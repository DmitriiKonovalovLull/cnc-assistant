"""
Загрузка контента с SPA-сайтов через Playwright (выполнение JavaScript).
Используется для Sandvik, Kennametal, Iscar, Seco, Walter и др.
"""

import asyncio
import logging
from typing import Optional, List
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None  # type: ignore
    Browser = None  # type: ignore
    Page = None  # type: ignore


async def fetch_via_playwright_search(
    base_url: str,
    query: str,
    search_input_selector: str,
    search_submit_selector: Optional[str] = None,
    results_container_selector: Optional[str] = None,
    wait_after_sec: float = 3.0,
) -> Optional[str]:
    """
    Открыть сайт, ввести запрос в поле поиска, дождаться контента и вернуть HTML.
    
    Args:
        base_url: Базовая URL сайта (например https://www.sandvik.coromant.com)
        query: Поисковый запрос
        search_input_selector: CSS-селектор поля ввода (например input[name="q"])
        search_submit_selector: Селектор кнопки отправки (опционально)
        results_container_selector: Селектор контейнера результатов (для ожидания)
        wait_after_sec: Секунды ожидания после ввода
        
    Returns:
        HTML страницы (после загрузки JS) или None
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.debug("Playwright not installed; SPA search skipped")
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(1.0)
                # Ищем поле поиска (может быть несколько селекторов)
                selectors = [s.strip() for s in search_input_selector.split(",")]
                input_el = None
                for sel in selectors:
                    try:
                        input_el = await page.query_selector(sel)
                        if input_el:
                            break
                    except Exception:
                        continue
                if not input_el:
                    logger.debug(f"Playwright: search input not found on {base_url}")
                    return None
                await input_el.fill(query)
                if search_submit_selector:
                    submit = await page.query_selector(search_submit_selector)
                    if submit:
                        await submit.click()
                else:
                    await input_el.press("Enter")
                if results_container_selector:
                    try:
                        await page.wait_for_selector(
                            results_container_selector,
                            timeout=int(wait_after_sec * 1000) + 2000,
                        )
                    except Exception:
                        pass
                await asyncio.sleep(wait_after_sec)
                content = await page.content()
                return content
            finally:
                await browser.close()
    except Exception as e:
        logger.debug(f"Playwright search failed {base_url}: {e}")
        return None
    return None


async def fetch_url_playwright(url: str, wait_sec: float = 2.0) -> Optional[str]:
    """
    Открыть URL в headless Chrome и вернуть HTML после выполнения JS.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=20000)
                await asyncio.sleep(wait_sec)
                return await page.content()
            finally:
                await browser.close()
    except Exception as e:
        logger.debug(f"Playwright fetch failed {url}: {e}")
        return None
