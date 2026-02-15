"""
СИСТЕМЫ МАРКИРОВКИ МАТЕРИАЛОВ.
Поддержка ГОСТ, GB/T, ASTM/SAE, EN/DIN и соответствий между ними.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MaterialEquivalent:
    """Эквивалент материала в разных системах маркировки."""
    gost: Optional[str] = None  # ГОСТ (Россия)
    gb: Optional[str] = None  # GB/T (Китай)
    astm_sae: Optional[str] = None  # ASTM/SAE (США)
    en_din: Optional[str] = None  # EN/DIN (Европа)
    iso: Optional[str] = None  # ISO (международный)
    jis: Optional[str] = None  # JIS (Япония)
    
    # Характеристики материала
    material_group: str = "steel"  # steel, stainless_steel, aluminum, titanium, etc.
    machinability: Optional[float] = None  # Показатель обрабатываемости (%, относительно эталона)
    description: Optional[str] = None
    
    def get_all_standards(self) -> Dict[str, Optional[str]]:
        """Получить все стандарты в виде словаря."""
        return {
            'gost': self.gost,
            'gb': self.gb,
            'astm_sae': self.astm_sae,
            'en_din': self.en_din,
            'iso': self.iso,
            'jis': self.jis
        }


class MaterialStandardsDatabase:
    """База данных соответствий материалов между системами маркировки."""
    
    # Таблица соответствий сталей
    STEEL_EQUIVALENTS: List[MaterialEquivalent] = [
        # Углеродистые конструкционные стали
        MaterialEquivalent(
            gost="Ст3", gb="08, 08КП", astm_sae="1008", en_din="S235JR / St37-2",
            material_group="steel", machinability=75.0,
            description="Низкоуглеродистая конструкционная сталь"
        ),
        MaterialEquivalent(
            gost="Ст10", gb="10", astm_sae="1010", en_din="C10, 1.0301",
            material_group="steel", machinability=80.0,
            description="Низкоуглеродистая сталь"
        ),
        MaterialEquivalent(
            gost="20", gb="20", astm_sae="1020", en_din="C22, 1.0402",
            material_group="steel", machinability=75.0,
            description="Углеродистая конструкционная сталь"
        ),
        MaterialEquivalent(
            gost="Ст45", gb="45", astm_sae="1045", en_din="C45, 1.0503",
            material_group="steel", machinability=65.0,
            description="Среднеуглеродистая конструкционная сталь"
        ),
        MaterialEquivalent(
            gost="35", gb="35", astm_sae="1035", en_din="C35, 1.0501",
            material_group="steel", machinability=70.0,
            description="Среднеуглеродистая сталь"
        ),
        
        # Легированные стали
        MaterialEquivalent(
            gost="40Х", gb="40Cr", astm_sae="5140", en_din="41Cr4, 1.7035",
            material_group="steel", machinability=60.0,
            description="Хромистая конструкционная сталь"
        ),
        MaterialEquivalent(
            gost="30ХГСА", gb="30CrMnSiA", astm_sae="4130", en_din="30CrMo4, 1.7220",
            material_group="steel", machinability=58.0,
            description="Хромомарганцево-кремнистая сталь"
        ),
        MaterialEquivalent(
            gost="14ХГСА", gb="14CrMnSiA", astm_sae="4130", en_din="14CrMnSi, 1.7220",
            material_group="steel", machinability=60.0,
            description="Низколегированная конструкционная сталь"
        ),
        
        # Нержавеющие стали
        MaterialEquivalent(
            gost="12Х18Н10Т", gb="—", astm_sae="321", en_din="X10CrNiTi18-9, 1.4541",
            material_group="stainless_steel", machinability=50.0,
            description="Нержавеющая сталь аустенитного класса"
        ),
        MaterialEquivalent(
            gost="08Х18Н10", gb="—", astm_sae="304", en_din="X5CrNi18-10, 1.4301",
            material_group="stainless_steel", machinability=55.0,
            description="Нержавеющая сталь аустенитного класса"
        ),
        MaterialEquivalent(
            gost="10Х17Н13М2Т", gb="—", astm_sae="316", en_din="X5CrNiMo17-12-2, 1.4401",
            material_group="stainless_steel", machinability=45.0,
            description="Нержавеющая сталь с молибденом"
        ),
        
        # Алюминиевые сплавы
        MaterialEquivalent(
            gost="Д16Т", gb="2A12-T4", astm_sae="2024", en_din="EN AW-2024",
            material_group="aluminum", machinability=400.0,
            description="Алюминиевый сплав с медью и магнием"
        ),
        MaterialEquivalent(
            gost="АМг6", gb="5A06", astm_sae="5056", en_din="EN AW-5056",
            material_group="aluminum", machinability=350.0,
            description="Алюминиево-магниевый сплав"
        ),
        MaterialEquivalent(
            gost="—", gb="6061", astm_sae="6061", en_din="EN AW-6061",
            material_group="aluminum", machinability=380.0,
            description="Алюминиевый сплав для механической обработки"
        ),
        MaterialEquivalent(
            gost="—", gb="7075", astm_sae="7075", en_din="EN AW-7075",
            material_group="aluminum", machinability=320.0,
            description="Высокопрочный алюминиевый сплав"
        ),
        
        # Титан
        MaterialEquivalent(
            gost="ВТ6", gb="TC4", astm_sae="Ti-6Al-4V", en_din="Ti-6Al-4V",
            material_group="titanium", machinability=30.0,
            description="Титановый сплав Grade 5"
        ),
        MaterialEquivalent(
            gost="ВТ1", gb="TA1", astm_sae="Grade 1", en_din="Ti-99.5",
            material_group="titanium", machinability=35.0,
            description="Чистый титан"
        ),
        
        # Чугун
        MaterialEquivalent(
            gost="СЧ20", gb="HT200", astm_sae="—", en_din="GG-20, EN-GJL-200",
            material_group="cast_iron", machinability=85.0,
            description="Серый чугун"
        ),
        MaterialEquivalent(
            gost="СЧ25", gb="HT250", astm_sae="—", en_din="GG-25, EN-GJL-250",
            material_group="cast_iron", machinability=80.0,
            description="Серый чугун повышенной прочности"
        ),
        
        # Латунь
        MaterialEquivalent(
            gost="Л63", gb="H63", astm_sae="C27000", en_din="CuZn37, CW508L",
            material_group="brass", machinability=150.0,
            description="Латунь деформируемая"
        ),
    ]
    
    @classmethod
    def find_equivalent(cls, material_name: str, standard: Optional[str] = None) -> Optional[MaterialEquivalent]:
        """
        Найти эквивалент материала по названию в любой системе маркировки.
        
        Args:
            material_name: Название материала (может быть в любой системе)
            standard: Предпочтительная система для поиска (gost, gb, astm_sae, en_din)
            
        Returns:
            MaterialEquivalent или None если не найдено
        """
        material_name_upper = material_name.upper().strip()
        material_name_lower = material_name.lower().strip()
        
        for equiv in cls.STEEL_EQUIVALENTS:
            # Проверяем все стандарты
            standards = equiv.get_all_standards()
            
            for std_name, std_value in standards.items():
                if std_value:
                    # Нормализуем значение для сравнения
                    std_values = [v.strip() for v in std_value.split('/') if v.strip()]
                    
                    for std_val in std_values:
                        # Убираем пробелы и приводим к верхнему регистру
                        std_val_clean = std_val.replace(' ', '').upper()
                        material_clean = material_name_upper.replace(' ', '')
                        
                        # Прямое совпадение
                        if std_val_clean == material_clean or std_val in material_name_upper:
                            return equiv
                        
                        # Частичное совпадение (для сложных обозначений)
                        if std_val_clean in material_clean or material_clean in std_val_clean:
                            if len(std_val_clean) >= 3:  # Минимум 3 символа для надежности
                                return equiv
        
        return None
    
    @classmethod
    def get_all_equivalents(cls, material_name: str) -> Dict[str, Optional[str]]:
        """
        Получить все эквиваленты материала во всех системах маркировки.
        
        Args:
            material_name: Название материала в любой системе
            
        Returns:
            Словарь с эквивалентами по системам
        """
        equiv = cls.find_equivalent(material_name)
        if equiv:
            return equiv.get_all_standards()
        return {}
    
    @classmethod
    def get_machinability(cls, material_name: str) -> Optional[float]:
        """
        Получить показатель обрабатываемости (machinability) материала.
        
        Args:
            material_name: Название материала
            
        Returns:
            Показатель machinability (%) или None
        """
        equiv = cls.find_equivalent(material_name)
        if equiv:
            return equiv.machinability
        return None
    
    @classmethod
    def get_material_info(cls, material_name: str) -> Optional[Dict[str, any]]:
        """
        Получить полную информацию о материале.
        
        Args:
            material_name: Название материала
            
        Returns:
            Словарь с информацией о материале
        """
        equiv = cls.find_equivalent(material_name)
        if equiv:
            return {
                'equivalents': equiv.get_all_standards(),
                'material_group': equiv.material_group,
                'machinability': equiv.machinability,
                'description': equiv.description
            }
        return None
    
    @classmethod
    def format_equivalents(cls, material_name: str) -> str:
        """
        Форматировать эквиваленты материала для отображения пользователю.
        
        Args:
            material_name: Название материала
            
        Returns:
            Отформатированная строка с эквивалентами
        """
        equiv = cls.find_equivalent(material_name)
        if not equiv:
            return f"❌ Материал '{material_name}' не найден в базе соответствий."
        
        lines = [f"📌 <b>Материал:</b> {material_name}\n"]
        
        if equiv.description:
            lines.append(f"📝 <b>Описание:</b> {equiv.description}\n")
        
        lines.append("🌍 <b>Эквиваленты по системам маркировки:</b>\n")
        
        if equiv.gost:
            lines.append(f"🇷🇺 <b>ГОСТ:</b> {equiv.gost}")
        if equiv.gb:
            lines.append(f"🇨🇳 <b>GB/T:</b> {equiv.gb}")
        if equiv.astm_sae:
            lines.append(f"🇺🇸 <b>ASTM/SAE:</b> {equiv.astm_sae}")
        if equiv.en_din:
            lines.append(f"🇪🇺 <b>EN/DIN:</b> {equiv.en_din}")
        if equiv.iso:
            lines.append(f"🌐 <b>ISO:</b> {equiv.iso}")
        if equiv.jis:
            lines.append(f"🇯🇵 <b>JIS:</b> {equiv.jis}")
        
        if equiv.machinability:
            lines.append(f"\n⚙️ <b>Обрабатываемость (Machinability):</b> {equiv.machinability:.0f}%")
            if equiv.machinability >= 100:
                lines.append("   ✅ Очень легко обрабатывается")
            elif equiv.machinability >= 70:
                lines.append("   ✅ Хорошо обрабатывается")
            elif equiv.machinability >= 50:
                lines.append("   ⚠️ Средняя обрабатываемость")
            else:
                lines.append("   ⚠️ Трудно обрабатывается")
        
        return "\n".join(lines)
