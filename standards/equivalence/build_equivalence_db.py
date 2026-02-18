"""
Построение базы данных эквивалентности стандартов.
Собирает данные из всех источников, строит граф связей, сохраняет в оптимизированный формат.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Путь к файлам данных
EQUIVALENCE_DATA_FILE = Path(__file__).parent / "equivalence_data.json"
EQUIVALENCE_DB_FILE = Path(__file__).parent / "equivalence_db.json"
OUTPUT_DB_FILE = Path(__file__).parent / "equivalence_db_optimized.json"


class EquivalenceDBBuilder:
    """
    Построитель базы данных эквивалентности.
    Собирает данные из всех источников и строит оптимизированный граф связей.
    """

    def __init__(self):
        self.equivalence_data: Dict[str, Any] = {}
        self.equivalence_db: Dict[str, Any] = {}
        self.graph: Dict[str, Set[str]] = defaultdict(set)  # Граф связей: стандарт -> множество аналогов
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)  # Обратный граф для быстрого поиска

    def load_data(self) -> None:
        """Загрузить данные из equivalence_data.json и equivalence_db.json."""
        # Загружаем equivalence_data.json
        if EQUIVALENCE_DATA_FILE.exists():
            try:
                with open(EQUIVALENCE_DATA_FILE, "r", encoding="utf-8") as f:
                    self.equivalence_data = json.load(f)
                logger.info(f"Loaded equivalence_data.json: {len(self.equivalence_data.get('equivalence_tables', {}))} tables")
            except Exception as e:
                logger.error(f"Failed to load equivalence_data.json: {e}")
        
        # Загружаем equivalence_db.json
        if EQUIVALENCE_DB_FILE.exists():
            try:
                with open(EQUIVALENCE_DB_FILE, "r", encoding="utf-8") as f:
                    self.equivalence_db = json.load(f)
                logger.info(f"Loaded equivalence_db.json")
            except Exception as e:
                logger.error(f"Failed to load equivalence_db.json: {e}")

    def build_graph(self) -> None:
        """
        Построить граф связей между стандартами.
        Узлы: стандарты в формате "SYSTEM:NUMBER"
        Рёбра: связи эквивалентности
        """
        logger.info("Building equivalence graph...")
        
        # Обрабатываем таблицы соответствия из equivalence_data.json
        equivalence_tables = self.equivalence_data.get("equivalence_tables", {})
        for table_name, table_data in equivalence_tables.items():
            mappings = table_data.get("mappings", [])
            for mapping in mappings:
                self._add_mapping_to_graph(mapping, table_name)
        
        # Обрабатываем таблицы соответствия из equivalence_db.json
        equivalence_mappings = self.equivalence_db.get("equivalence_mappings", {})
        for table_name, mappings in equivalence_mappings.items():
            for mapping in mappings:
                self._add_mapping_to_graph(mapping, table_name)
        
        # Обрабатываем быстрые поиски (thread_equivalents, tolerance_equivalents)
        self._process_quick_lookups()
        
        logger.info(f"Graph built: {len(self.graph)} nodes, {sum(len(neighbors) for neighbors in self.graph.values())} edges")

    def _add_mapping_to_graph(self, mapping: Dict[str, Any], table_name: str) -> None:
        """Добавить маппинг в граф связей."""
        # Извлекаем системы и номера из маппинга
        nodes = []
        for key, value in mapping.items():
            if key in ["gost", "iso", "din", "gb", "jis", "ansi", "asme", "bs", "nf", "uni"]:
                if value:
                    node = f"{key.upper()}:{value}"
                    nodes.append(node)
        
        # Создаём связи между всеми узлами (полный граф для группы эквивалентов)
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i+1:]:
                self.graph[node1].add(node2)
                self.graph[node2].add(node1)
                self.reverse_graph[node1].add(node2)
                self.reverse_graph[node2].add(node1)

    def _process_quick_lookups(self) -> None:
        """Обработать быстрые поиски и добавить в граф."""
        # Thread equivalents
        thread_equivs = self.equivalence_db.get("thread_equivalents", {})
        for thread_designation, systems in thread_equivs.items():
            nodes = []
            for system, number in systems.items():
                if number:
                    node = f"{system.upper()}:{number}"
                    nodes.append(node)
            
            # Связываем все системы для этого обозначения резьбы
            for i, node1 in enumerate(nodes):
                for node2 in nodes[i+1:]:
                    self.graph[node1].add(node2)
                    self.graph[node2].add(node1)
        
        # Tolerance equivalents
        tolerance_equivs = self.equivalence_db.get("tolerance_equivalents", {})
        for tolerance_designation, systems in tolerance_equivs.items():
            nodes = []
            for system, number in systems.items():
                if number:
                    node = f"{system.upper()}:{number}"
                    nodes.append(node)
            
            for i, node1 in enumerate(nodes):
                for node2 in nodes[i+1:]:
                    self.graph[node1].add(node2)
                    self.graph[node2].add(node1)

    def find_all_equivalents(self, system: str, number: str) -> List[Dict[str, Any]]:
        """
        Найти все аналоги стандарта через граф связей.
        
        Args:
            system: Система стандарта (GOST, ISO, etc.)
            number: Номер стандарта
            
        Returns:
            Список словарей с информацией об аналогах
        """
        node = f"{system.upper()}:{number}"
        if node not in self.graph:
            return []
        
        equivalents = []
        for neighbor in self.graph[node]:
            neighbor_system, neighbor_number = neighbor.split(":", 1)
            equivalents.append({
                "system": neighbor_system,
                "number": neighbor_number,
                "confidence": 0.8,  # Можно улучшить на основе исходных данных
            })
        
        return equivalents

    def find_path(self, system1: str, number1: str, system2: str, number2: str) -> Optional[List[str]]:
        """
        Найти путь между двумя стандартами в графе (BFS).
        
        Args:
            system1, number1: Первый стандарт
            system2, number2: Второй стандарт
            
        Returns:
            Список узлов пути или None если путь не найден
        """
        start = f"{system1.upper()}:{number1}"
        end = f"{system2.upper()}:{number2}"
        
        if start == end:
            return [start]
        
        if start not in self.graph or end not in self.graph:
            return None
        
        # BFS для поиска кратчайшего пути
        queue = [(start, [start])]
        visited = {start}
        
        while queue:
            current, path = queue.pop(0)
            
            for neighbor in self.graph[current]:
                if neighbor == end:
                    return path + [neighbor]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None

    def build_optimized_db(self) -> Dict[str, Any]:
        """
        Построить оптимизированную базу данных для быстрого поиска.
        
        Returns:
            Оптимизированная структура данных
        """
        logger.info("Building optimized database...")
        
        optimized = {
            "version": "1.0",
            "metadata": {
                "total_nodes": len(self.graph),
                "total_edges": sum(len(neighbors) for neighbors in self.graph.values()) // 2,
                "systems": list(set(node.split(":")[0] for node in self.graph.keys())),
            },
            "by_system": {},  # Индексация по системам
            "by_category": {},  # Индексация по категориям
            "quick_lookup": {},  # Быстрый поиск по обозначениям
            "graph": {},  # Граф связей (сериализованный)
        }
        
        # Индексация по системам
        for node in self.graph.keys():
            system, number = node.split(":", 1)
            if system not in optimized["by_system"]:
                optimized["by_system"][system] = []
            optimized["by_system"][system].append(number)
        
        # Индексация по категориям (из исходных данных)
        categories = defaultdict(list)
        equivalence_tables = self.equivalence_data.get("equivalence_tables", {})
        equivalence_mappings = self.equivalence_db.get("equivalence_mappings", {})
        
        for table_data in list(equivalence_tables.values()) + list(equivalence_mappings.values()):
            mappings = table_data if isinstance(table_data, list) else table_data.get("mappings", [])
            for mapping in mappings:
                category = mapping.get("category", "unknown")
                for key, value in mapping.items():
                    if key in ["gost", "iso", "din", "gb", "jis", "ansi"] and value:
                        node = f"{key.upper()}:{value}"
                        if node not in categories[category]:
                            categories[category].append(node)
        
        optimized["by_category"] = {cat: list(nodes) for cat, nodes in categories.items()}
        
        # Быстрый поиск по обозначениям
        optimized["quick_lookup"] = {
            "threads": self.equivalence_db.get("thread_equivalents", {}),
            "tolerances": self.equivalence_db.get("tolerance_equivalents", {}),
        }
        
        # Граф связей (сериализованный как список списков для компактности)
        optimized["graph"] = {
            node: list(neighbors) for node, neighbors in self.graph.items()
        }
        
        return optimized

    def save_optimized_db(self, output_file: Optional[Path] = None) -> None:
        """
        Сохранить оптимизированную базу данных в JSON файл.
        
        Args:
            output_file: Путь к выходному файлу (по умолчанию equivalence_db_optimized.json)
        """
        output_file = output_file or OUTPUT_DB_FILE
        
        optimized_db = self.build_optimized_db()
        
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(optimized_db, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved optimized database to {output_file}")
            logger.info(f"  Nodes: {optimized_db['metadata']['total_nodes']}")
            logger.info(f"  Edges: {optimized_db['metadata']['total_edges']}")
            logger.info(f"  Systems: {len(optimized_db['metadata']['systems'])}")
        except Exception as e:
            logger.error(f"Failed to save optimized database: {e}")

    def build(self) -> Dict[str, Any]:
        """
        Главный метод: собрать данные, построить граф, оптимизировать.
        
        Returns:
            Оптимизированная база данных
        """
        logger.info("Starting equivalence database build...")
        
        # 1. Загружаем данные
        self.load_data()
        
        # 2. Строим граф связей
        self.build_graph()
        
        # 3. Строим оптимизированную БД
        optimized_db = self.build_optimized_db()
        
        # 4. Сохраняем
        self.save_optimized_db()
        
        logger.info("Equivalence database build completed")
        return optimized_db

    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику по построенной базе данных."""
        stats = {
            "total_nodes": len(self.graph),
            "total_edges": sum(len(neighbors) for neighbors in self.graph.values()) // 2,
            "systems": {},
            "categories": {},
        }
        
        # Статистика по системам
        for node in self.graph.keys():
            system = node.split(":")[0]
            stats["systems"][system] = stats["systems"].get(system, 0) + 1
        
        return stats


def main():
    """Главная функция для запуска построения базы данных."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    builder = EquivalenceDBBuilder()
    optimized_db = builder.build()
    
    stats = builder.get_statistics()
    print("\n=== Equivalence Database Statistics ===")
    print(f"Total nodes: {stats['total_nodes']}")
    print(f"Total edges: {stats['total_edges']}")
    print(f"\nNodes by system:")
    for system, count in sorted(stats["systems"].items()):
        print(f"  {system}: {count}")
    
    # Примеры поиска
    print("\n=== Example Queries ===")
    equivalents = builder.find_all_equivalents("GOST", "24705")
    print(f"GOST 24705 equivalents: {len(equivalents)} found")
    for eq in equivalents[:3]:
        print(f"  - {eq['system']} {eq['number']}")
    
    path = builder.find_path("GOST", "24705", "ISO", "965-1")
    if path:
        print(f"\nPath GOST 24705 -> ISO 965-1: {' -> '.join(path)}")


if __name__ == "__main__":
    main()
