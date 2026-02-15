"""
Конфигурация сайтов для умного парсера.
У каждого производителя — свой способ поиска (SPA vs статика, свои URL/формы).
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class SearchStrategy(Enum):
    """Как искать на сайте."""
    URL_GET = "url_get"       # GET /search?q=... (статичная страница)
    URL_GET_PAGE = "url_get_page"  # GET страницы каталога/продукта
    PLAYWRIGHT = "playwright"  # SPA: ввод в поиск, ожидание контента
    API = "api"              # Прямой вызов API (если известен endpoint)


@dataclass
class SiteConfig:
    """Конфиг одного сайта."""
    id: str
    name: str
    base_url: str
    needs_js: bool  # SPA — нужен Playwright
    strategy: SearchStrategy
    # Для URL_GET: шаблон поиска (например /search?q={query})
    search_url_template: Optional[str] = None
    # Для PLAYWRIGHT: селектор поля поиска, опционально селектор контейнера результатов
    search_input_selector: Optional[str] = None
    search_submit_selector: Optional[str] = None
    results_container_selector: Optional[str] = None
    # Таймаут ожидания контента (сек)
    wait_after_search_sec: float = 3.0
    # Доп. заголовки
    extra_headers: dict = field(default_factory=dict)


# Сайты инструментов (Sandvik, Kennametal, Iscar, Seco, Walter) — все SPA
TOOL_SITES: List[SiteConfig] = [
    SiteConfig(
        id="sandvik",
        name="Sandvik Coromant",
        base_url="https://www.sandvik.coromant.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_url_template=None,
        search_input_selector='input[type="search"], input[name="q"], input[placeholder*="earch" i], [data-testid="search-input"]',
        search_submit_selector='button[type="submit"], [aria-label*="earch" i]',
        results_container_selector="main, [role='main'], .search-results, .product-list, .results",
        wait_after_search_sec=4.0,
    ),
    SiteConfig(
        id="kennametal",
        name="Kennametal",
        base_url="https://www.kennametal.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"], input[placeholder*="earch" i]',
        search_submit_selector='button[type="submit"]',
        results_container_selector="main, [role='main'], .search-results, .product-grid",
        wait_after_search_sec=4.0,
    ),
    SiteConfig(
        id="iscar",
        name="Iscar",
        base_url="https://www.iscar.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"], input[placeholder*="earch" i]',
        search_submit_selector='button[type="submit"]',
        results_container_selector="main, [role='main'], .search-results, .products",
        wait_after_search_sec=4.0,
    ),
    SiteConfig(
        id="seco",
        name="Seco Tools",
        base_url="https://www.secotools.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"], input[placeholder*="earch" i]',
        search_submit_selector='button[type="submit"]',
        results_container_selector="main, [role='main'], .search-results",
        wait_after_search_sec=4.0,
    ),
    SiteConfig(
        id="walter",
        name="Walter Tools",
        base_url="https://www.walter-tools.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"], input[placeholder*="earch" i]',
        search_submit_selector='button[type="submit"]',
        results_container_selector="main, [role='main'], .search-results",
        wait_after_search_sec=4.0,
    ),
]

# Сайты станков — часто есть статические страницы или отдельные домены
MACHINE_SITES: List[SiteConfig] = [
    SiteConfig(
        id="haas",
        name="Haas",
        base_url="https://www.haascnc.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"]',
        search_submit_selector='button[type="submit"]',
        results_container_selector="main, [role='main'], .search-results",
        wait_after_search_sec=3.0,
    ),
    SiteConfig(
        id="mazak",
        name="Mazak",
        base_url="https://www.mazak.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"]',
        results_container_selector="main, [role='main']",
        wait_after_search_sec=3.0,
    ),
    SiteConfig(
        id="okuma",
        name="Okuma",
        base_url="https://www.okuma.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"]',
        results_container_selector="main, [role='main']",
        wait_after_search_sec=3.0,
    ),
    SiteConfig(
        id="dmgmori",
        name="DMG Mori",
        base_url="https://www.dmgmori.com",
        needs_js=True,
        strategy=SearchStrategy.PLAYWRIGHT,
        search_input_selector='input[type="search"], input[name="q"]',
        results_container_selector="main, [role='main']",
        wait_after_search_sec=3.0,
    ),
]


def get_tool_sites(use_playwright: bool = True) -> List[SiteConfig]:
    """Сайты для поиска инструментов. Если Playwright недоступен — вернуть только те, что с url_get (пока таких нет)."""
    if use_playwright:
        return list(TOOL_SITES)
    return [s for s in TOOL_SITES if not s.needs_js]


def get_machine_sites(use_playwright: bool = True) -> List[SiteConfig]:
    """Сайты для поиска станков."""
    if use_playwright:
        return list(MACHINE_SITES)
    return [s for s in MACHINE_SITES if not s.needs_js]
