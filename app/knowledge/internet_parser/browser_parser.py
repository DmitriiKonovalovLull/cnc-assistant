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
import hashlib
import time
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import quote_plus, urlparse
from datetime import datetime, timedelta
from dataclasses import dataclass, field

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

# Импорты с явной обработкой ошибок
try:
    from app.knowledge.internet_parser.fetch_aiohttp import fetch_html_aiohttp, AIOHTTP_AVAILABLE
    AIOHTTP_AVAILABLE = AIOHTTP_AVAILABLE and fetch_html_aiohttp is not None
except ImportError as e:
    logger.debug(f"AIOHTTP import failed: {e}")
    AIOHTTP_AVAILABLE = False
    fetch_html_aiohttp = None

try:
    from app.knowledge.internet_parser.fetch_playwright import (
        fetch_via_playwright_search,
        fetch_url_playwright,
        PLAYWRIGHT_AVAILABLE,
    )
    PLAYWRIGHT_AVAILABLE = PLAYWRIGHT_AVAILABLE and fetch_via_playwright_search is not None
except ImportError as e:
    logger.debug(f"Playwright import failed: {e}")
    PLAYWRIGHT_AVAILABLE = False
    fetch_via_playwright_search = None
    fetch_url_playwright = None


@dataclass
class ParserMetrics:
    """Метрики парсинга для мониторинга."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    total_time_ms: float = 0.0
    site_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def reset(self):
        """Сбросить метрики."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.timeout_requests = 0
        self.total_time_ms = 0.0
        self.site_stats.clear()


class DomainRateLimiter:
    """Ограничитель частоты запросов к доменам."""
    
    def __init__(self, delay_seconds: float = 2.0):
        """
        Инициализация rate limiter.
        
        Args:
            delay_seconds: Минимальная задержка между запросами к одному домену
        """
        self._last_request: Dict[str, datetime] = {}
        self._delay = delay_seconds
    
    def _extract_domain(self, url: str) -> str:
        """Извлечь домен из URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc or parsed.path.split('/')[0]
        except Exception:
            return url.split('/')[0]
    
    async def wait_if_needed(self, domain: str) -> None:
        """
        Подождать, если не прошло достаточно времени с последнего запроса к домену.
        
        Args:
            domain: Домен для проверки
        """
        last = self._last_request.get(domain)
        if last:
            elapsed = (datetime.now() - last).total_seconds()
            if elapsed < self._delay:
                wait_time = self._delay - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
                await asyncio.sleep(wait_time)
        self._last_request[domain] = datetime.now()


def _validate_extracted_data(data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
    """
    Валидировать и очистить извлеченные данные.
    
    Args:
        data: Извлеченные данные
        data_type: Тип данных ('tool', 'machine', 'operation')
        
    Returns:
        Валидированные данные
    """
    validated = {}
    
    if data_type == 'tool':
        # Проверка радиуса пластины (типичные значения 0.2-3.2 мм)
        if 'insert_radius_mm' in data:
            try:
                radius = float(data['insert_radius_mm'])
                if 0.1 <= radius <= 10.0:
                    validated['insert_radius_mm'] = radius
                else:
                    logger.warning(f"Invalid insert radius: {radius} (expected 0.1-10.0)")
            except (ValueError, TypeError):
                logger.warning(f"Invalid insert_radius_mm value: {data['insert_radius_mm']}")
                
        # Проверка скорости резания
        if 'vc_m_min' in data:
            try:
                vc = float(data['vc_m_min'])
                if 10 <= vc <= 1000:  # Типичный диапазон для металлообработки
                    validated['vc_m_min'] = vc
                else:
                    logger.warning(f"Invalid vc_m_min: {vc} (expected 10-1000)")
            except (ValueError, TypeError):
                logger.warning(f"Invalid vc_m_min value: {data['vc_m_min']}")
                
    elif data_type == 'machine':
        # Проверка мощности (не 0 и не космическая)
        if 'power_kw' in data:
            try:
                power = float(data['power_kw'])
                if 0.1 <= power <= 500:
                    validated['power_kw'] = power
                else:
                    logger.warning(f"Invalid power_kw: {power} (expected 0.1-500)")
            except (ValueError, TypeError):
                logger.warning(f"Invalid power_kw value: {data['power_kw']}")
                
        # Проверка оборотов
        if 'max_rpm' in data:
            try:
                rpm = int(data['max_rpm'])
                if 10 <= rpm <= 50000:
                    validated['max_rpm'] = rpm
                else:
                    logger.warning(f"Invalid max_rpm: {rpm} (expected 10-50000)")
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_rpm value: {data['max_rpm']}")
    
    # Копируем остальные поля без валидации
    for key, value in data.items():
        if key not in validated:
            validated[key] = value
            
    return validated


def _merge_tool_data(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Умное объединение данных об инструменте из разных источников.
    
    Args:
        existing: Существующие данные
        new: Новые данные
        
    Returns:
        Объединенные данные
    """
    merged = existing.copy()
    
    # Для числовых полей можно брать среднее если значения близки
    numeric_fields = ['insert_radius_mm', 'vc_m_min', 'feed_mm_rev']
    for field in numeric_fields:
        if field in existing and field in new:
            try:
                existing_val = float(existing[field])
                new_val = float(new[field])
                # Если значения близки (разница < 20%) - берем среднее
                if existing_val > 0 and abs(existing_val - new_val) / existing_val < 0.2:
                    merged[field] = (existing_val + new_val) / 2
                    logger.debug(f"Merged {field}: {existing_val} and {new_val} -> {merged[field]}")
                else:
                    # Если сильно отличаются - логируем и берем существующее
                    logger.info(f"Conflict in {field}: {existing_val} vs {new_val}, keeping {existing_val}")
            except (ValueError, TypeError):
                pass
                
    # Для строковых полей можно объединять
    if 'material' in existing and 'material' in new:
        materials = set(str(existing['material']).split(', ')) | set(str(new['material']).split(', '))
        merged['material'] = ', '.join(sorted(materials))
        
    # Обновляем новыми полями которых нет в существующих
    for key, value in new.items():
        if key not in merged:
            merged[key] = value
            
    return merged


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


class BrowserParser:
    """
    Умный парсер: aiohttp + Playwright (SPA), посайтовая конфигурация, контекстное извлечение.
    
    Поддерживает:
    - Таймауты для защиты от зависаний
    - Ограничение параллельных запросов
    - Кэширование результатов
    - Rate limiting для защиты от блокировки
    - Метрики для мониторинга
    - Валидацию извлеченных данных
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        per_site_timeout: int = 30,
        cache_ttl_seconds: int = 3600,
        rate_limit_delay: float = 2.0,
        max_retries: int = 2
    ):
        """
        Инициализация парсера.
        
        Args:
            max_concurrent: Максимальное количество параллельных запросов
            per_site_timeout: Таймаут для одного сайта в секундах
            cache_ttl_seconds: Время жизни кэша в секундах
            rate_limit_delay: Задержка между запросами к одному домену в секундах
            max_retries: Максимальное количество повторов при ошибке
        """
        self._aiohttp_ok = AIOHTTP_AVAILABLE
        self._playwright_ok = PLAYWRIGHT_AVAILABLE
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._per_site_timeout = per_site_timeout
        self._rate_limiter = DomainRateLimiter(delay_seconds=rate_limit_delay)
        self._max_retries = max_retries
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = cache_ttl_seconds
        self.metrics = ParserMetrics()
        
        if not self._aiohttp_ok:
            logger.warning("aiohttp not available. Install: pip install aiohttp")
        if not self._playwright_ok:
            logger.warning(
                "Playwright not available for SPA sites. "
                "Install: pip install -r requirements_internet.txt && playwright install"
            )
    
    def _get_cache_key(self, search_type: str, query: str) -> str:
        """
        Создать ключ кэша.
        
        Args:
            search_type: Тип поиска ('tool', 'machine', 'operation')
            query: Поисковый запрос
            
        Returns:
            MD5 хэш ключа кэша
        """
        key_data = f"{search_type}:{query.lower().strip()}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Получить из кэша, если не истек TTL.
        
        Args:
            key: Ключ кэша
            
        Returns:
            Данные из кэша или None
        """
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry['timestamp'] < timedelta(seconds=self._cache_ttl):
                logger.debug(f"Cache hit for key {key[:8]}...")
                return entry['data']
            else:
                # TTL истек - удаляем из кэша
                del self._cache[key]
                logger.debug(f"Cache expired for key {key[:8]}...")
        return None
    
    def _save_to_cache(self, key: str, data: Dict[str, Any]) -> None:
        """
        Сохранить в кэш.
        
        Args:
            key: Ключ кэша
            data: Данные для сохранения
        """
        self._cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }
        logger.debug(f"Cached result for key {key[:8]}...")
    
    async def _fetch_one_site_with_timeout(
        self,
        site: SiteConfig,
        query: str,
        rate_limiter: DomainRateLimiter
    ) -> Tuple[SiteConfig, Optional[str]]:
        """
        Загрузить один сайт с таймаутом и rate limiting.
        
        Args:
            site: Конфигурация сайта
            query: Поисковый запрос
            rate_limiter: Rate limiter для доменов
            
        Returns:
            Кортеж (site_config, html_content)
        """
        # Извлекаем домен для rate limiting
        domain = rate_limiter._extract_domain(site.base_url)
        await rate_limiter.wait_if_needed(domain)
        
        try:
            html = await asyncio.wait_for(
                _fetch_for_site(site, query),
                timeout=self._per_site_timeout
            )
            if html:
                logger.debug(f"Successfully fetched {site.id} ({site.name})")
            else:
                logger.debug(f"No content fetched from {site.id} ({site.name})")
            return (site, html)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {site.id} ({site.name}) after {self._per_site_timeout}s")
            self.metrics.timeout_requests += 1
            return (site, None)
        except Exception as e:
            logger.warning(f"Fetch failed for {site.id} ({site.name}): {e}")
            return (site, None)
    
    async def _fetch_one_site_with_limit(
        self,
        site: SiteConfig,
        query: str,
        rate_limiter: DomainRateLimiter
    ) -> Tuple[SiteConfig, Optional[str]]:
        """
        Загрузить сайт с учетом лимита параллельных запросов и retry логики.
        
        Args:
            site: Конфигурация сайта
            query: Поисковый запрос
            rate_limiter: Rate limiter для доменов
            
        Returns:
            Кортеж (site_config, html_content)
        """
        async with self._semaphore:
            # Retry логика
            last_error = None
            for attempt in range(self._max_retries + 1):
                try:
                    return await self._fetch_one_site_with_timeout(site, query, rate_limiter)
                except Exception as e:
                    last_error = e
                    if attempt < self._max_retries:
                        wait_time = (attempt + 1) * 2  # Экспоненциальная задержка
                        logger.debug(f"Retry {attempt + 1}/{self._max_retries} for {site.id} after {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"All retries failed for {site.id}: {last_error}")
                        return (site, None)
            return (site, None)
    
    async def _fetch_all_sites(
        self,
        sites: List[SiteConfig],
        query: str
    ) -> List[Tuple[SiteConfig, Optional[str]]]:
        """
        Параллельно загрузить все сайты с таймаутами и ограничениями.
        
        Args:
            sites: Список сайтов для загрузки
            query: Поисковый запрос
            
        Returns:
            Список кортежей (site_config, html_content)
        """
        tasks = [
            self._fetch_one_site_with_limit(site, query, self._rate_limiter)
            for site in sites
        ]
        # Используем return_exceptions=True чтобы не прерывать выполнение при ошибке одного сайта
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Обрабатываем результаты и исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Exception in fetch task for {sites[i].id}: {result}")
                processed_results.append((sites[i], None))
            else:
                processed_results.append(result)
        return processed_results

    async def search_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Поиск информации об инструменте.
        Параллельный опрос сайтов; для SPA — Playwright (поиск по форме).
        Извлечение — контекстное (радиус/материал/mark/VC из нужных секций).
        
        Args:
            tool_name: Название инструмента
            
        Returns:
            Результат поиска с данными и источниками
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        # Проверяем кэш
        cache_key = self._get_cache_key('tool', tool_name)
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.info(f"Returning cached result for tool '{tool_name}'")
            self.metrics.successful_requests += 1
            return cached
        
        result: Dict[str, Any] = {
            "success": False,
            "tool_name": tool_name,
            "found_data": {},
            "sources": [],
        }
        if not self._aiohttp_ok and not self._playwright_ok:
            result["error"] = "Neither aiohttp nor Playwright available"
            self.metrics.failed_requests += 1
            return result

        sites = get_tool_sites(use_playwright=self._playwright_ok)
        if not sites:
            self.metrics.failed_requests += 1
            return result

        try:
            logger.info(f"Searching tool info for '{tool_name}' across {len(sites)} sites")
            results = await self._fetch_all_sites(sites, tool_name)
            successful_fetches = sum(1 for _, html in results if html)
            logger.info(f"Fetched content from {successful_fetches}/{len(sites)} sites")
            
            merged_data = {}
            for site, html in results:
                if not html:
                    continue
                try:
                    extracted = extract_tool_data_context_aware(html, tool_name)
                    if extracted:
                        # Валидируем извлеченные данные
                        validated = _validate_extracted_data(extracted, 'tool')
                        if validated:
                            # Умное объединение данных из разных источников
                            if merged_data:
                                merged_data = _merge_tool_data(merged_data, validated)
                            else:
                                merged_data = validated
                            result["sources"].append(site.base_url)
                            
                            # Обновляем статистику по сайтам
                            domain = self._rate_limiter._extract_domain(site.base_url)
                            if domain not in self.metrics.site_stats:
                                self.metrics.site_stats[domain] = {'success': 0, 'total': 0, 'timeout': 0}
                            self.metrics.site_stats[domain]['total'] += 1
                            self.metrics.site_stats[domain]['success'] += 1
                            
                            logger.info(f"Extracted data from {site.id} ({site.name})")
                except Exception as e:
                    logger.warning(f"Error extracting data from {site.id}: {e}")
                    domain = self._rate_limiter._extract_domain(site.base_url)
                    if domain not in self.metrics.site_stats:
                        self.metrics.site_stats[domain] = {'success': 0, 'total': 0, 'timeout': 0}
                    self.metrics.site_stats[domain]['total'] += 1
            
            if merged_data:
                result["found_data"] = merged_data
                result["success"] = True
                self.metrics.successful_requests += 1
                # Сохраняем в кэш только успешные результаты
                self._save_to_cache(cache_key, result)
            else:
                self.metrics.failed_requests += 1
                
        except Exception as e:
            logger.error(f"Error searching tool info: {e}", exc_info=True)
            result["error"] = str(e)
            self.metrics.failed_requests += 1
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.total_time_ms += elapsed_ms

        return result

    async def search_machine_info(self, machine_name: str) -> Dict[str, Any]:
        """
        Поиск информации о станке.
        Мощность и обороты извлекаются только из контекста шпинделя/привода.
        
        Args:
            machine_name: Название станка
            
        Returns:
            Результат поиска с данными и источниками
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        # Проверяем кэш
        cache_key = self._get_cache_key('machine', machine_name)
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.info(f"Returning cached result for machine '{machine_name}'")
            self.metrics.successful_requests += 1
            return cached
        
        result: Dict[str, Any] = {
            "success": False,
            "machine_name": machine_name,
            "found_data": {},
            "sources": [],
        }
        if not self._aiohttp_ok and not self._playwright_ok:
            result["error"] = "Neither aiohttp nor Playwright available"
            self.metrics.failed_requests += 1
            return result

        sites = get_machine_sites(use_playwright=self._playwright_ok)
        if not sites:
            self.metrics.failed_requests += 1
            return result

        try:
            logger.info(f"Searching machine info for '{machine_name}' across {len(sites)} sites")
            results = await self._fetch_all_sites(sites, machine_name)
            successful_fetches = sum(1 for _, html in results if html)
            logger.info(f"Fetched content from {successful_fetches}/{len(sites)} sites")
            
            merged_data = {}
            for site, html in results:
                if not html:
                    continue
                try:
                    extracted = extract_machine_data_context_aware(html, machine_name)
                    if extracted:
                        # Валидируем извлеченные данные
                        validated = _validate_extracted_data(extracted, 'machine')
                        if validated:
                            # Умное объединение данных
                            if merged_data:
                                merged_data = _merge_tool_data(merged_data, validated)  # Используем ту же функцию
                            else:
                                merged_data = validated
                            result["sources"].append(site.base_url)
                            
                            # Обновляем статистику
                            domain = self._rate_limiter._extract_domain(site.base_url)
                            if domain not in self.metrics.site_stats:
                                self.metrics.site_stats[domain] = {'success': 0, 'total': 0, 'timeout': 0}
                            self.metrics.site_stats[domain]['total'] += 1
                            self.metrics.site_stats[domain]['success'] += 1
                            
                            logger.info(f"Extracted data from {site.id} ({site.name})")
                except Exception as e:
                    logger.warning(f"Error extracting data from {site.id}: {e}")
                    domain = self._rate_limiter._extract_domain(site.base_url)
                    if domain not in self.metrics.site_stats:
                        self.metrics.site_stats[domain] = {'success': 0, 'total': 0, 'timeout': 0}
                    self.metrics.site_stats[domain]['total'] += 1
            
            if merged_data:
                result["found_data"] = merged_data
                result["success"] = True
                self.metrics.successful_requests += 1
                # Сохраняем в кэш только успешные результаты
                self._save_to_cache(cache_key, result)
            else:
                self.metrics.failed_requests += 1
                
        except Exception as e:
            logger.error(f"Error searching machine info: {e}", exc_info=True)
            result["error"] = str(e)
            self.metrics.failed_requests += 1
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.total_time_ms += elapsed_ms

        return result

    async def search_operation_info(
        self, operation_type: str, material: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Поиск режимов резания для типа операции (и опционально материала).
        Контекстное извлечение vc_min/vc_max из секций про скорость резания.
        
        Args:
            operation_type: Тип операции
            material: Материал (опционально)
            
        Returns:
            Результат поиска с данными и источниками
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        query = f"{operation_type} режимы резания"
        if material:
            query += f" {material}"
        
        # Проверяем кэш
        cache_key = self._get_cache_key('operation', query)
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.info(f"Returning cached result for operation '{operation_type}'")
            self.metrics.successful_requests += 1
            return cached
        
        result: Dict[str, Any] = {
            "success": False,
            "operation_type": operation_type,
            "material": material,
            "found_data": {},
            "sources": [],
        }
        if not self._aiohttp_ok and not self._playwright_ok:
            result["error"] = "Neither aiohttp nor Playwright available"
            self.metrics.failed_requests += 1
            return result

        # Используем те же сайты инструментов — там есть разделы по режимам
        sites = get_tool_sites(use_playwright=self._playwright_ok)
        if not sites:
            self.metrics.failed_requests += 1
            return result

        try:
            logger.info(f"Searching operation info for '{operation_type}' (material: {material}) across {len(sites)} sites")
            results = await self._fetch_all_sites(sites, query)
            successful_fetches = sum(1 for _, html in results if html)
            logger.info(f"Fetched content from {successful_fetches}/{len(sites)} sites")
            
            merged_data = {}
            for site, html in results:
                if not html:
                    continue
                try:
                    extracted = extract_operation_data_context_aware(
                        html, operation_type, material or ""
                    )
                    if extracted:
                        # Валидируем извлеченные данные
                        validated = _validate_extracted_data(extracted, 'tool')  # Используем валидацию инструмента
                        if validated:
                            # Умное объединение данных
                            if merged_data:
                                merged_data = _merge_tool_data(merged_data, validated)
                            else:
                                merged_data = validated
                            result["sources"].append(site.base_url)
                            
                            # Обновляем статистику
                            domain = self._rate_limiter._extract_domain(site.base_url)
                            if domain not in self.metrics.site_stats:
                                self.metrics.site_stats[domain] = {'success': 0, 'total': 0, 'timeout': 0}
                            self.metrics.site_stats[domain]['total'] += 1
                            self.metrics.site_stats[domain]['success'] += 1
                            
                            logger.info(f"Extracted data from {site.id} ({site.name})")
                except Exception as e:
                    logger.warning(f"Error extracting data from {site.id}: {e}")
                    domain = self._rate_limiter._extract_domain(site.base_url)
                    if domain not in self.metrics.site_stats:
                        self.metrics.site_stats[domain] = {'success': 0, 'total': 0, 'timeout': 0}
                    self.metrics.site_stats[domain]['total'] += 1
            
            if merged_data:
                result["found_data"] = merged_data
                result["success"] = True
                self.metrics.successful_requests += 1
                # Сохраняем в кэш только успешные результаты
                self._save_to_cache(cache_key, result)
            else:
                self.metrics.failed_requests += 1
                
        except Exception as e:
            logger.error(f"Error searching operation info: {e}", exc_info=True)
            result["error"] = str(e)
            self.metrics.failed_requests += 1
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            self.metrics.total_time_ms += elapsed_ms

        return result
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Получить сводку метрик парсинга.
        
        Returns:
            Словарь с метриками
        """
        avg_time = (
            self.metrics.total_time_ms / self.metrics.total_requests
            if self.metrics.total_requests > 0
            else 0.0
        )
        
        success_rate = (
            (self.metrics.successful_requests / self.metrics.total_requests * 100)
            if self.metrics.total_requests > 0
            else 0.0
        )
        
        return {
            'total_requests': self.metrics.total_requests,
            'successful_requests': self.metrics.successful_requests,
            'failed_requests': self.metrics.failed_requests,
            'timeout_requests': self.metrics.timeout_requests,
            'success_rate_percent': round(success_rate, 2),
            'avg_time_ms': round(avg_time, 2),
            'total_time_ms': round(self.metrics.total_time_ms, 2),
            'site_stats': dict(self.metrics.site_stats),
            'cache_size': len(self._cache)
        }