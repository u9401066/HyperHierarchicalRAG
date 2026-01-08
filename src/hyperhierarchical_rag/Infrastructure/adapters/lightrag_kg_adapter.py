"""
LightRAG Knowledge Graph Adapter

連接 LightRAG 的 Knowledge Graph，實現與 HGMem Memory 的雙向同步。
這是整合的關鍵橋樑。

對應 HGMem 原始碼中的 knowledge_graph_inst 參數：
- evolve() 中使用 knowledge_graph_inst.has_node(), get_node()
- collect_absent_entities_relationships() 中使用 upsert_node(), upsert_edge()
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple, cast, runtime_checkable


@runtime_checkable
class IKnowledgeGraph(Protocol):
    """Knowledge Graph 介面協議 - 定義必須實現的方法"""

    async def has_node(self, entity_name: str) -> bool:
        """檢查實體是否存在"""
        ...

    async def get_node(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """獲取實體數據"""
        ...

    async def get_neighbor_nodes(self, entity_name: str) -> List[str]:
        """獲取鄰居節點名稱"""
        ...

    async def upsert_node(self, entity_name: str, node_data: Dict[str, Any]) -> None:
        """插入或更新實體"""
        ...

    async def upsert_edge(self, src_id: str, tgt_id: str, edge_data: Dict[str, Any]) -> None:
        """插入或更新關係邊"""
        ...


@dataclass
class LightRAGKGAdapter:
    """
    LightRAG Knowledge Graph 適配器

    將 LightRAG 的 graph_storage (NetworkXStorage 或其他) 包裝成
    HGMem 期望的 knowledge_graph_inst 介面。

    Usage:
        from lightrag import LightRAG

        rag = LightRAG(working_dir="./rag_cache")
        kg_adapter = LightRAGKGAdapter(rag.chunk_entity_relation_graph)

        # 現在可以用於 EnhancedMemoryEvolver
        evolver.set_kg_adapter(kg_adapter)
    """

    graph_storage: Any  # LightRAG 的 BaseGraphStorage 實例
    _cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _cache_enabled: bool = field(default=True)

    async def has_node(self, entity_name: str) -> bool:
        """
        檢查實體是否存在於 Knowledge Graph

        Args:
            entity_name: 實體名稱 (會自動轉大寫)

        Returns:
            bool: 是否存在
        """
        entity_name = entity_name.upper()

        # 先檢查快取
        if self._cache_enabled and entity_name in self._cache:
            return True

        # 調用 LightRAG graph storage
        if hasattr(self.graph_storage, "has_node"):
            result = await self.graph_storage.has_node(entity_name)
            return bool(result)

        # Fallback: 嘗試 get_node
        try:
            node = await self.get_node(entity_name)
            return node is not None
        except Exception:
            return False

    async def get_node(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """
        獲取實體的完整數據

        Args:
            entity_name: 實體名稱

        Returns:
            實體數據字典，包含:
            - entity_type: 實體類型
            - description: 描述
            - source_id: 來源 chunk ID
        """
        entity_name = entity_name.upper()

        # 先檢查快取
        if self._cache_enabled and entity_name in self._cache:
            return self._cache[entity_name]

        # 調用 LightRAG graph storage
        if hasattr(self.graph_storage, "get_node"):
            node_data = await self.graph_storage.get_node(entity_name)
            if node_data and self._cache_enabled:
                self._cache[entity_name] = node_data
            return cast(Dict[str, Any] | None, node_data)

        return None

    async def get_neighbor_nodes(self, entity_name: str) -> List[str]:
        """
        獲取實體的所有鄰居節點

        用於 get_extended_info() 擴展記憶點的上下文

        Args:
            entity_name: 實體名稱

        Returns:
            鄰居節點名稱列表
        """
        entity_name = entity_name.upper()

        if hasattr(self.graph_storage, "get_neighbor_nodes"):
            res = await self.graph_storage.get_neighbor_nodes(entity_name)
            return cast(List[str], res)

        # Fallback: 使用 edge iteration
        if hasattr(self.graph_storage, "_graph"):
            graph = self.graph_storage._graph
            if entity_name in graph:
                return list(graph.neighbors(entity_name))

        return []

    async def get_node_edges(self, entity_name: str) -> List[Dict[str, Any]]:
        """
        獲取與實體相關的所有邊

        Args:
            entity_name: 實體名稱

        Returns:
            邊數據列表，每個包含 src_id, tgt_id, description, keywords 等
        """
        entity_name = entity_name.upper()
        edges = []

        if hasattr(self.graph_storage, "get_node_edges"):
            res = await self.graph_storage.get_node_edges(entity_name)
            return cast(List[Dict[str, Any]], res)

        # Fallback: 遍歷鄰居獲取邊
        neighbors = await self.get_neighbor_nodes(entity_name)
        for neighbor in neighbors:
            edge_data = await self.get_edge(entity_name, neighbor)
            if edge_data:
                edges.append({"src_id": entity_name, "tgt_id": neighbor, **edge_data})

        return edges

    async def get_edge(self, src_id: str, tgt_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取兩個實體之間的邊數據

        Args:
            src_id: 源實體
            tgt_id: 目標實體

        Returns:
            邊數據字典
        """
        src_id = src_id.upper()
        tgt_id = tgt_id.upper()

        if hasattr(self.graph_storage, "get_edge"):
            res = await self.graph_storage.get_edge(src_id, tgt_id)
            return cast(Dict[str, Any] | None, res)

        return None

    async def upsert_node(self, entity_name: str, node_data: Dict[str, Any]) -> None:
        """
        插入或更新實體

        用於 collect_absent_entities_relationships() 補全缺失實體

        Args:
            entity_name: 實體名稱
            node_data: 實體數據，包含 entity_type, description, source_id
        """
        entity_name = entity_name.upper()

        # 更新快取
        if self._cache_enabled:
            self._cache[entity_name] = node_data

        # 調用 LightRAG graph storage
        if hasattr(self.graph_storage, "upsert_node"):
            await self.graph_storage.upsert_node(entity_name, node_data=node_data)

    async def upsert_edge(self, src_id: str, tgt_id: str, edge_data: Dict[str, Any]) -> None:
        """
        插入或更新關係邊

        用於 collect_absent_entities_relationships() 補全缺失關係

        Args:
            src_id: 源實體
            tgt_id: 目標實體
            edge_data: 邊數據，包含 description, keywords, weight, source_id
        """
        src_id = src_id.upper()
        tgt_id = tgt_id.upper()

        if hasattr(self.graph_storage, "upsert_edge"):
            await self.graph_storage.upsert_edge(src_id, tgt_id, edge_data=edge_data)

    async def delete_node(self, entity_name: str) -> None:
        """刪除實體"""
        entity_name = entity_name.upper()

        # 清除快取
        if entity_name in self._cache:
            del self._cache[entity_name]

        if hasattr(self.graph_storage, "delete_node"):
            await self.graph_storage.delete_node(entity_name)

    # ========== 批量操作 ==========

    async def batch_get_nodes(self, entity_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量獲取多個實體

        Args:
            entity_names: 實體名稱列表

        Returns:
            {entity_name: node_data} 字典
        """
        results = {}
        tasks = [self.get_node(name) for name in entity_names]
        nodes = await asyncio.gather(*tasks, return_exceptions=True)

        for name, node in zip(entity_names, nodes):
            if isinstance(node, dict):
                results[name.upper()] = node

        return results

    async def batch_upsert_nodes(self, nodes: Dict[str, Dict[str, Any]]) -> None:
        """
        批量插入/更新實體

        Args:
            nodes: {entity_name: node_data} 字典
        """
        tasks = [self.upsert_node(name, data) for name, data in nodes.items()]
        await asyncio.gather(*tasks)

    async def batch_upsert_edges(self, edges: List[Dict[str, Any]]) -> None:
        """
        批量插入/更新邊

        Args:
            edges: 邊數據列表，每個包含 src_id, tgt_id 和其他數據
        """
        tasks = []
        for edge in edges:
            src_id = edge.pop("src_id")
            tgt_id = edge.pop("tgt_id")
            tasks.append(self.upsert_edge(src_id, tgt_id, edge))

        await asyncio.gather(*tasks)

    # ========== 查詢統計 ==========

    async def get_all_nodes(self) -> List[str]:
        """獲取所有實體名稱"""
        if hasattr(self.graph_storage, "get_all_nodes"):
            res = await self.graph_storage.get_all_nodes()
            return cast(List[str], res)

        if hasattr(self.graph_storage, "_graph"):
            return list(self.graph_storage._graph.nodes())

        return []

    async def get_node_count(self) -> int:
        """獲取實體數量"""
        nodes = await self.get_all_nodes()
        return len(nodes)

    async def get_edge_count(self) -> int:
        """獲取邊數量"""
        if hasattr(self.graph_storage, "_graph"):
            return int(self.graph_storage._graph.number_of_edges())
        return 0

    def clear_cache(self) -> None:
        """清除快取"""
        self._cache.clear()

    # ========== 上下文管理 ==========

    async def __aenter__(self) -> "LightRAGKGAdapter":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.clear_cache()


class InMemoryKGAdapter(LightRAGKGAdapter):
    """
    In-Memory Knowledge Graph 適配器

    用於測試或不需要 LightRAG 的場景
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        self._adjacency: Dict[str, List[str]] = {}
        super().__init__(graph_storage=None, _cache_enabled=False)

    async def has_node(self, entity_name: str) -> bool:
        return entity_name.upper() in self._nodes

    async def get_node(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self._nodes.get(entity_name.upper())

    async def get_neighbor_nodes(self, entity_name: str) -> List[str]:
        return self._adjacency.get(entity_name.upper(), [])

    async def upsert_node(self, entity_name: str, node_data: Dict[str, Any]) -> None:
        entity_name = entity_name.upper()
        self._nodes[entity_name] = node_data
        if entity_name not in self._adjacency:
            self._adjacency[entity_name] = []

    async def upsert_edge(self, src_id: str, tgt_id: str, edge_data: Dict[str, Any]) -> None:
        src_id = src_id.upper()
        tgt_id = tgt_id.upper()

        self._edges[(src_id, tgt_id)] = edge_data

        # 更新鄰接表
        if src_id not in self._adjacency:
            self._adjacency[src_id] = []
        if tgt_id not in self._adjacency[src_id]:
            self._adjacency[src_id].append(tgt_id)

        # 雙向
        if tgt_id not in self._adjacency:
            self._adjacency[tgt_id] = []
        if src_id not in self._adjacency[tgt_id]:
            self._adjacency[tgt_id].append(src_id)

    async def get_edge(self, src_id: str, tgt_id: str) -> Optional[Dict[str, Any]]:
        src_id = src_id.upper()
        tgt_id = tgt_id.upper()
        return self._edges.get((src_id, tgt_id)) or self._edges.get((tgt_id, src_id))

    async def delete_node(self, entity_name: str) -> None:
        entity_name = entity_name.upper()
        if entity_name in self._nodes:
            del self._nodes[entity_name]
        if entity_name in self._adjacency:
            del self._adjacency[entity_name]
        # 清除相關邊
        self._edges = {k: v for k, v in self._edges.items() if entity_name not in k}

    async def get_all_nodes(self) -> List[str]:
        return list(self._nodes.keys())

    async def get_node_count(self) -> int:
        return len(self._nodes)

    async def get_edge_count(self) -> int:
        return len(self._edges)
