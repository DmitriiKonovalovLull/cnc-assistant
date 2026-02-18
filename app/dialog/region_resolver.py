"""
Region Resolver - определение региона пользователя для стандартов.
Поддерживает: Россия (RU), Европа (EU), Китай (CN).
"""

import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class Region(Enum):
    """Регионы для стандартов."""
    RU = "ru"  # Россия: ГОСТ, ОСТ
    EU = "eu"  # Европа: EN, DIN, ISO
    CN = "cn"  # Китай: GB, GB/T
    US = "us"  # США: ANSI, ASME (для будущего расширения)
    JP = "jp"  # Япония: JIS (для будущего расширения)


class StandardFamily:
    """Семейства стандартов по регионам."""
    
    # Региональные стандарты
    REGIONAL_STANDARDS = {
        Region.RU: ['ГОСТ', 'GOST', 'ОСТ', 'OST'],
        Region.EU: ['EN', 'DIN', 'ISO'],
        Region.CN: ['GB', 'GB/T'],
        Region.US: ['ANSI', 'ASME'],
        Region.JP: ['JIS'],
    }
    
    # Международные стандарты (доступны везде)
    INTERNATIONAL = ['ISO']  # ISO используется и в EU, и в других регионах


class RegionResolver:
    """
    Резолвер региона пользователя.
    Определяет регион на основе:
    1. Явного указания пользователя
    2. Языка интерфейса
    3. Стандарта в запросе
    4. Геолокации (если доступна)
    """
    
    # Маппинг языка на регион
    LANG_TO_REGION = {
        'ru': Region.RU,
        'en': Region.EU,  # По умолчанию для английского - Европа
        'zh': Region.CN,
    }
    
    def __init__(self):
        """Инициализация резолвера."""
        pass
    
    def resolve(
        self,
        user_id: int,
        lang: Optional[str] = None,
        standard_family: Optional[str] = None,
        user_region: Optional[Region] = None
    ) -> Region:
        """
        Определить регион пользователя.
        
        Args:
            user_id: ID пользователя
            lang: Язык интерфейса
            standard_family: Семейство стандарта в запросе
            user_region: Явно указанный регион пользователя
            
        Returns:
            Определенный регион
        """
        # 1. Явное указание пользователя (высший приоритет)
        if user_region:
            return user_region
        
        # 2. По стандарту в запросе
        if standard_family:
            region = self._get_region_by_standard(standard_family)
            if region:
                return region
        
        # 3. По языку интерфейса
        if lang:
            region = self.LANG_TO_REGION.get(lang)
            if region:
                return region
        
        # 4. По умолчанию - Россия (основной рынок)
        return Region.RU
    
    def _get_region_by_standard(self, standard_family: str) -> Optional[Region]:
        """
        Определить регион по семейству стандарта.
        
        Args:
            standard_family: Семейство стандарта (ГОСТ, DIN, GB и т.д.)
            
        Returns:
            Регион или None
        """
        standard_family_upper = standard_family.upper()
        
        for region, families in StandardFamily.REGIONAL_STANDARDS.items():
            if standard_family_upper in families:
                return region
        
        return None
    
    def get_standards_for_region(self, region: Region) -> list:
        """
        Получить список стандартов для региона.
        
        Args:
            region: Регион
            
        Returns:
            Список семейств стандартов
        """
        standards = StandardFamily.REGIONAL_STANDARDS.get(region, [])
        # Добавляем международные стандарты
        standards.extend(StandardFamily.INTERNATIONAL)
        return standards
    
    def is_standard_available_in_region(self, standard_family: str, region: Region) -> bool:
        """
        Проверить доступность стандарта в регионе.
        
        Args:
            standard_family: Семейство стандарта
            region: Регион
            
        Returns:
            True если стандарт доступен в регионе
        """
        # Международные стандарты доступны везде
        if standard_family.upper() in StandardFamily.INTERNATIONAL:
            return True
        
        # Проверяем региональные стандарты
        regional_standards = StandardFamily.REGIONAL_STANDARDS.get(region, [])
        return standard_family.upper() in regional_standards
