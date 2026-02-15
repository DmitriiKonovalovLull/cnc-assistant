"""
СЕРВИС ЗНАНИЙ - работа с базой знаний и интернет-данными.
Ищет материал/инструмент, подгружает данные, нормализует названия.
Интернет НЕ отвечает пользователю напрямую - только обогащает базу знаний.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.services.cache_service import cached
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Импортируем модуль соответствий материалов
try:
    from app.knowledge.material_standards import MaterialStandardsDatabase
except ImportError:
    MaterialStandardsDatabase = None
    logger.warning("MaterialStandardsDatabase not available")


@dataclass
class MaterialData:
    """Данные о материале."""
    name: str
    normalized_name: str
    material_type: str
    hardness_hb: Optional[float] = None
    tensile_strength: Optional[float] = None
    recommended_vc_min: Optional[float] = None
    recommended_vc_max: Optional[float] = None
    kc_factor: Optional[float] = None  # Удельная сила резания


@dataclass
class ToolData:
    """Данные об инструменте."""
    tool_type: str
    material: str
    insert_radius_mm: Optional[float] = None
    recommended_vc_multiplier: float = 1.0
    recommended_feed_multiplier: float = 1.0
    max_depth_of_cut_mm: Optional[float] = None


@dataclass
class MachineData:
    """Данные о станке."""
    machine_type: str
    power_kw: Optional[float] = None
    max_rpm: Optional[float] = None
    typical_power_kw: Optional[float] = None


class KnowledgeService:
    """
    Сервис знаний для работы с базой знаний.
    """
    
    def __init__(self, database=None):
        """
        Инициализация сервиса знаний.
        
        Args:
            database: База данных (опционально, для будущего расширения)
        """
        self.database = database
        self.materials: Dict[str, MaterialData] = {}
        self.tools: Dict[str, ToolData] = {}
        self.machines: Dict[str, MachineData] = {}
        self.knowledge_base_path = Path("app/knowledge/knowledge_base")
    
    async def initialize(self) -> None:
        """Инициализация - загрузка базы знаний."""
        logger.info("Loading knowledge base...")
        
        # Создаем директории если нет
        self.knowledge_base_path.mkdir(parents=True, exist_ok=True)
        
        # Загружаем данные
        await self._load_materials()
        await self._load_tools()
        await self._load_machines()
        
        logger.info(f"Knowledge base loaded: {len(self.materials)} materials, "
                   f"{len(self.tools)} tools, {len(self.machines)} machines")
    
    async def _load_materials(self) -> None:
        """Загрузить материалы из базы знаний."""
        materials_file = self.knowledge_base_path / "materials.json"
        
        if materials_file.exists():
            try:
                with open(materials_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for mat_data in data.get('materials', []):
                        material = MaterialData(**mat_data)
                        self.materials[material.normalized_name.lower()] = material
            except Exception as e:
                logger.warning(f"Failed to load materials: {e}")
        
        # Если файла нет, создаем базовые данные
        if not self.materials:
            self._create_default_materials()
    
    async def _load_tools(self) -> None:
        """Загрузить инструменты из базы знаний."""
        tools_file = self.knowledge_base_path / "tools.json"
        
        if tools_file.exists():
            try:
                with open(tools_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for tool_data in data.get('tools', []):
                        tool = ToolData(**tool_data)
                        key = f"{tool.tool_type}_{tool.material}".lower()
                        self.tools[key] = tool
            except Exception as e:
                logger.warning(f"Failed to load tools: {e}")
        
        # Если файла нет, создаем базовые данные
        if not self.tools:
            self._create_default_tools()
    
    async def _load_machines(self) -> None:
        """Загрузить станки из базы знаний."""
        machines_file = self.knowledge_base_path / "machines.json"
        
        if machines_file.exists():
            try:
                with open(machines_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for machine_data in data.get('machines', []):
                        machine = MachineData(**machine_data)
                        self.machines[machine.machine_type.lower()] = machine
            except Exception as e:
                logger.warning(f"Failed to load machines: {e}")
        
        # Если файла нет, создаем базовые данные
        if not self.machines:
            self._create_default_machines()
    
    def _create_default_materials(self) -> None:
        """Создать базовые материалы."""
        default_materials = [
            MaterialData(
                name="сталь",
                normalized_name="сталь",
                material_type="steel",
                hardness_hb=200.0,
                tensile_strength=600.0,
                recommended_vc_min=80.0,
                recommended_vc_max=200.0,
                kc_factor=2000.0
            ),
            MaterialData(
                name="алюминий",
                normalized_name="алюминий",
                material_type="aluminum",
                hardness_hb=50.0,
                tensile_strength=300.0,
                recommended_vc_min=200.0,
                recommended_vc_max=500.0,
                kc_factor=800.0
            ),
            MaterialData(
                name="нержавейка",
                normalized_name="нержавейка",
                material_type="stainless_steel",
                hardness_hb=180.0,
                tensile_strength=600.0,
                recommended_vc_min=50.0,
                recommended_vc_max=120.0,
                kc_factor=2500.0
            ),
            MaterialData(
                name="титан",
                normalized_name="титан",
                material_type="titanium",
                hardness_hb=350.0,
                tensile_strength=900.0,
                recommended_vc_min=20.0,
                recommended_vc_max=60.0,
                kc_factor=3000.0
            )
        ]
        
        for material in default_materials:
            self.materials[material.normalized_name.lower()] = material
    
    def _create_default_tools(self) -> None:
        """Создать базовые инструменты."""
        default_tools = [
            ToolData(
                tool_type="токарный проходной",
                material="твердый сплав",
                insert_radius_mm=0.8,
                recommended_vc_multiplier=1.0,
                recommended_feed_multiplier=1.0,
                max_depth_of_cut_mm=6.0
            ),
            ToolData(
                tool_type="токарный чистовой",
                material="твердый сплав",
                insert_radius_mm=0.4,
                recommended_vc_multiplier=1.2,
                recommended_feed_multiplier=0.7,
                max_depth_of_cut_mm=1.0
            )
        ]
        
        for tool in default_tools:
            key = f"{tool.tool_type}_{tool.material}".lower()
            self.tools[key] = tool
    
    def _create_default_machines(self) -> None:
        """Создать базовые станки."""
        default_machines = [
            MachineData(
                machine_type="токарный ЧПУ",
                power_kw=11.0,
                max_rpm=3000.0,
                typical_power_kw=11.0
            ),
            MachineData(
                machine_type="токарный ручной",
                power_kw=7.5,
                max_rpm=2000.0,
                typical_power_kw=7.5
            ),
            MachineData(
                machine_type="фрезерный ЧПУ",
                power_kw=15.0,
                max_rpm=8000.0,
                typical_power_kw=15.0
            )
        ]
        
        for machine in default_machines:
            self.machines[machine.machine_type.lower()] = machine
    
    def find_material(self, material_name: str) -> Optional[MaterialData]:
        """
        Найти материал по имени.
        
        Args:
            material_name: Название материала
            
        Returns:
            Данные о материале или None
        """
        material_lower = material_name.lower()
        
        # Прямой поиск
        if material_lower in self.materials:
            return self.materials[material_lower]
        
        # Поиск по частичному совпадению
        for normalized_name, material in self.materials.items():
            if normalized_name in material_lower or material_lower in normalized_name:
                return material
        
        # Пробуем найти через систему соответствий материалов
        if MaterialStandardsDatabase:
            equiv = MaterialStandardsDatabase.find_equivalent(material_name)
            if equiv:
                # Создаем MaterialData из эквивалента
                normalized_name = equiv.gost or equiv.astm_sae or equiv.en_din or material_name.lower()
                material_data = MaterialData(
                    name=material_name,
                    normalized_name=normalized_name.lower(),
                    material_type=equiv.material_group,
                    recommended_vc_min=self._get_vc_min_from_machinability(equiv.machinability),
                    recommended_vc_max=self._get_vc_max_from_machinability(equiv.machinability)
                )
                return material_data
        
        return None
    
    def _get_vc_min_from_machinability(self, machinability: Optional[float]) -> Optional[float]:
        """Получить минимальную скорость резания из machinability."""
        if machinability is None:
            return None
        # Базовое значение для machinability 100% = 150 м/мин
        base_vc = 150.0
        return base_vc * (machinability / 100.0) * 0.6  # Минимум
    
    def _get_vc_max_from_machinability(self, machinability: Optional[float]) -> Optional[float]:
        """Получить максимальную скорость резания из machinability."""
        if machinability is None:
            return None
        # Базовое значение для machinability 100% = 150 м/мин
        base_vc = 150.0
        return base_vc * (machinability / 100.0) * 1.4  # Максимум
    
    def get_material_equivalents(self, material_name: str) -> Dict[str, Optional[str]]:
        """
        Получить эквиваленты материала во всех системах маркировки.
        
        Args:
            material_name: Название материала
            
        Returns:
            Словарь с эквивалентами по системам
        """
        if MaterialStandardsDatabase:
            return MaterialStandardsDatabase.get_all_equivalents(material_name)
        return {}
    
    def get_material_machinability(self, material_name: str) -> Optional[float]:
        """
        Получить показатель обрабатываемости материала.
        
        Args:
            material_name: Название материала
            
        Returns:
            Показатель machinability (%) или None
        """
        if MaterialStandardsDatabase:
            return MaterialStandardsDatabase.get_machinability(material_name)
        return None
    
    def format_material_equivalents(self, material_name: str) -> str:
        """
        Форматировать эквиваленты материала для отображения.
        
        Args:
            material_name: Название материала
            
        Returns:
            Отформатированная строка с эквивалентами
        """
        if MaterialStandardsDatabase:
            return MaterialStandardsDatabase.format_equivalents(material_name)
        return f"❌ Система соответствий материалов недоступна."
    
    def find_tool(self, tool_type: str, tool_material: str) -> Optional[ToolData]:
        """
        Найти инструмент по типу и материалу.
        
        Args:
            tool_type: Тип инструмента
            tool_material: Материал инструмента
            
        Returns:
            Данные об инструменте или None
        """
        key = f"{tool_type}_{tool_material}".lower()
        
        if key in self.tools:
            return self.tools[key]
        
        # Поиск по частичному совпадению
        for tool_key, tool in self.tools.items():
            if tool_type.lower() in tool_key and tool_material.lower() in tool_key:
                return tool
        
        return None
    
    @cached(ttl_seconds=7200, key_prefix="knowledge.machine")
    def find_machine(self, machine_type: str) -> Optional[MachineData]:
        """
        Найти станок по типу.
        
        Args:
            machine_type: Тип станка
            
        Returns:
            Данные о станке или None
        """
        machine_lower = machine_type.lower()
        
        # Прямой поиск
        if machine_lower in self.machines:
            return self.machines[machine_lower]
        
        # Поиск по частичному совпадению
        for key, machine in self.machines.items():
            if key in machine_lower or machine_lower in key:
                return machine
        
        return None
    
    def list_machines(self) -> List[str]:
        """
        Получить список всех известных типов станков.
        
        Returns:
            Список названий типов станков
        """
        return list(self.machines.keys())
    
    def get_all_machines(self) -> Dict[str, MachineData]:
        """
        Получить все станки.
        
        Returns:
            Словарь со всеми станками
        """
        return self.machines.copy()
    
    def normalize_material_name(self, material_name: str) -> str:
        """
        Нормализовать название материала.
        
        Args:
            material_name: Исходное название
            
        Returns:
            Нормализованное название
        """
        material = self.find_material(material_name)
        if material:
            return material.normalized_name
        
        # Если не найден, возвращаем как есть (в нижнем регистре)
        return material_name.lower()
    
    def get_material_properties(self, material_name: str) -> Optional[Dict[str, Any]]:
        """
        Получить свойства материала.
        
        Args:
            material_name: Название материала
            
        Returns:
            Словарь со свойствами или None
        """
        material = self.find_material(material_name)
        if not material:
            return None
        
        return {
            'name': material.name,
            'normalized_name': material.normalized_name,
            'material_type': material.material_type,
            'hardness_hb': material.hardness_hb,
            'tensile_strength': material.tensile_strength,
            'recommended_vc_min': material.recommended_vc_min,
            'recommended_vc_max': material.recommended_vc_max,
            'kc_factor': material.kc_factor
        }
