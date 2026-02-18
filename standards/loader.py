"""
Модуль автозагрузки стандартов при старте приложения.
Загружает ГОСТ, ОСТ, ISO и другие стандарты в реестр.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def load_all_standards(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Загрузить все стандарты в реестр при старте приложения.
    
    Args:
        force_refresh: Если True, обновить данные из интернета
        
    Returns:
        Словарь с результатами загрузки
    """
    results = {
        "loaded": [],
        "errors": [],
        "warnings": [],
    }
    
    try:
        # Импортируем необходимые модули
        from standards.registry.world_registry import WorldStandardRegistry
        from standards.equivalence.equivalence_engine import EquivalenceEngine
        from standards.ingestion.fetch_gost_data import (
            load_gost_threads,
            load_iso_tolerances,
            update_all_data
        )
        from standards.equivalence.build_equivalence_db import EquivalenceDBBuilder
        
        logger.info("📐 Начало загрузки стандартов...")
        
        # 1. Загружаем данные ГОСТ и ISO (если нужно обновить)
        if force_refresh:
            logger.info("🔄 Обновление данных стандартов из интернета...")
            try:
                update_results = update_all_data()
                if update_results.get("errors"):
                    results["warnings"].extend(update_results["errors"])
                logger.info("✅ Данные обновлены")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обновить данные из интернета: {e}")
                results["warnings"].append(f"Не удалось обновить данные: {e}")
        
        # 2. Загружаем сохраненные данные ГОСТ
        try:
            gost_data = load_gost_threads()
            thread_count = len(gost_data.get("threads", []))
            logger.info(f"✅ Загружено ГОСТ резьб: {thread_count} записей")
            results["loaded"].append(f"ГОСТ резьбы: {thread_count}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки ГОСТ резьб: {e}")
            results["errors"].append(f"ГОСТ резьбы: {e}")
        
        # 3. Загружаем сохраненные данные ISO допусков
        try:
            iso_data = load_iso_tolerances()
            tolerance_grades = len(iso_data.get("tolerances", {}))
            logger.info(f"✅ Загружено ISO допусков: {tolerance_grades} классов")
            results["loaded"].append(f"ISO допуски: {tolerance_grades}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки ISO допусков: {e}")
            results["errors"].append(f"ISO допуски: {e}")
        
        # 4. Инициализируем реестр стандартов (он сам загрузит данные при первом использовании)
        try:
            registry = WorldStandardRegistry()
            logger.info("✅ Реестр стандартов инициализирован")
            results["loaded"].append("Реестр стандартов")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации реестра: {e}")
            results["errors"].append(f"Реестр: {e}")
        
        # 5. Инициализируем движок эквивалентности
        try:
            equivalence_engine = EquivalenceEngine()
            logger.info("✅ Движок эквивалентности инициализирован")
            results["loaded"].append("Движок эквивалентности")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации движка эквивалентности: {e}")
            results["errors"].append(f"Эквивалентность: {e}")
        
        # 6. Строим оптимизированную базу данных эквивалентности (если нужно)
        try:
            builder = EquivalenceDBBuilder()
            builder.load_data()
            builder.build_graph()
            logger.info("✅ База данных эквивалентности построена")
            results["loaded"].append("База эквивалентности")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось построить базу эквивалентности: {e}")
            results["warnings"].append(f"База эквивалентности: {e}")
        
        logger.info("📐 Загрузка стандартов завершена")
        
    except ImportError as e:
        error_msg = f"Не удалось импортировать модули стандартов: {e}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Критическая ошибка при загрузке стандартов: {e}"
        logger.exception(error_msg)
        results["errors"].append(error_msg)
    
    return results


def get_standards_status() -> Dict[str, Any]:
    """
    Получить статус загруженных стандартов.
    
    Returns:
        Словарь со статусом
    """
    status = {
        "registry_available": False,
        "equivalence_available": False,
        "gost_data_available": False,
        "iso_data_available": False,
    }
    
    try:
        from standards.registry.world_registry import WorldStandardRegistry
        registry = WorldStandardRegistry()
        status["registry_available"] = True
    except:
        pass
    
    try:
        from standards.equivalence.equivalence_engine import EquivalenceEngine
        engine = EquivalenceEngine()
        status["equivalence_available"] = True
    except:
        pass
    
    try:
        from standards.ingestion.fetch_gost_data import load_gost_threads
        data = load_gost_threads()
        if data.get("threads"):
            status["gost_data_available"] = True
    except:
        pass
    
    try:
        from standards.ingestion.fetch_gost_data import load_iso_tolerances
        data = load_iso_tolerances()
        if data.get("tolerances"):
            status["iso_data_available"] = True
    except:
        pass
    
    return status
