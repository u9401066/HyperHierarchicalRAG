"""
Vector Store Adapter

連接 LightRAG 的向量庫 (NanoVectorDB 或其他)，實現相似度搜尋。

HGMem 使用三個向量庫：
1. entities_vdb - 實體向量庫
2. relationships_vdb - 關係向量庫
3. text_chunks_vdb - 文本塊向量庫

這些用於：
- get_extended_info() 中的實體相似度搜尋
- get_memory_pointwise_related_info() 中的 text chunk 檢索
- collect_absent_entities_relationships() 中補全缺失實體/關係
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, cast, runtime_checkable


@runtime_checkable
class IVectorStore(Protocol):
    """Vector Store 介面協議"""

    async def query(
        self, query: str, top_k: int = 10, filter_lambda: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """向量相似度查詢"""
        ...

    async def upsert(self, data: Dict[str, Dict[str, Any]]) -> None:
        """插入或更新向量"""
        ...


@dataclass
class VectorStoreAdapter:
    """
    Vector Store 適配器

    將 LightRAG 的 vector_db_storage (NanoVectorDBStorage 等) 包裝成
    統一的向量查詢介面。

    Usage:
        from lightrag import LightRAG

        rag = LightRAG(working_dir="./rag_cache")

        entities_adapter = VectorStoreAdapter(
            vector_storage=rag.entities_vdb,
            namespace="entities"
        )

        # 相似度查詢
        results = await entities_adapter.query("machine learning", top_k=10)
    """

    vector_storage: Any  # LightRAG 的 BaseVectorStorage 實例
    namespace: str = "default"
    _embedding_func: Optional[Callable] = None

    async def query(
        self, query: str, top_k: int = 10, filter_lambda: Optional[Callable[[Dict], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度查詢

        Args:
            query: 查詢文本
            top_k: 返回前 K 個結果
            filter_lambda: 過濾函數，如 lambda data: data["__id__"] in valid_ids

        Returns:
            結果列表，每個包含:
            - id: 向量 ID
            - content: 原始內容
            - distance: 距離分數 (越小越相似)
            - 其他元數據
        """
        if self.vector_storage is None:
            return []

        if hasattr(self.vector_storage, "query"):
            # LightRAG 的向量庫查詢
            if filter_lambda:
                results = await self.vector_storage.query(
                    query, top_k=top_k, filter_lambda=filter_lambda
                )
            else:
                results = await self.vector_storage.query(query, top_k=top_k)
            return cast(List[Dict[str, Any]], results)

        return []

    async def upsert(self, data: Dict[str, Dict[str, Any]]) -> None:
        """
        插入或更新向量

        Args:
            data: {id: {content: str, ...metadata}} 字典
        """
        if self.vector_storage is None:
            return

        if hasattr(self.vector_storage, "upsert"):
            await self.vector_storage.upsert(data)

    async def delete(self, ids: List[str]) -> None:
        """刪除向量"""
        if self.vector_storage is None:
            return

        if hasattr(self.vector_storage, "delete"):
            await self.vector_storage.delete(ids)

    async def get_by_ids(self, ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """根據 ID 獲取向量數據"""
        if self.vector_storage is None:
            return {}

        if hasattr(self.vector_storage, "get_by_ids"):
            res = await self.vector_storage.get_by_ids(ids)
            return cast(Dict[str, Dict[str, Any]], res)

        return {}


@dataclass
class TextChunksAdapter:
    """
    Text Chunks 適配器

    用於存取文本塊 (KV Storage + Vector Storage)

    HGMem 中的用法：
    - text_chunks_db.get_by_id(chunk_id) - KV 存取
    - text_chunks_vdb.query(query, ...) - 向量查詢
    """

    kv_storage: Any  # LightRAG 的 BaseKVStorage 實例 (text_chunks)
    vector_storage: Any  # LightRAG 的 BaseVectorStorage 實例 (text_chunks_vdb)

    async def get_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        根據 ID 獲取文本塊

        Args:
            chunk_id: chunk ID

        Returns:
            文本塊數據，包含:
            - content: 文本內容
            - full_doc_id: 所屬文檔 ID
            - chunk_order_index: 在文檔中的順序
        """
        if self.kv_storage is None:
            return None

        if hasattr(self.kv_storage, "get_by_id"):
            res = await self.kv_storage.get_by_id(chunk_id)
            return cast(Dict[str, Any] | None, res)

        # Fallback
        if hasattr(self.kv_storage, "get"):
            res = await self.kv_storage.get(chunk_id)
            return cast(Dict[str, Any] | None, res)

        return None

    async def query(
        self, query: str, top_k: int = 10, filter_lambda: Optional[Callable[[Dict], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        向量相似度查詢文本塊

        Args:
            query: 查詢文本
            top_k: 返回前 K 個結果
            filter_lambda: 過濾函數

        Returns:
            結果列表
        """
        if self.vector_storage is None:
            return []

        if hasattr(self.vector_storage, "query"):
            if filter_lambda:
                res = await self.vector_storage.query(
                    query, top_k=top_k, filter_lambda=filter_lambda
                )
                return cast(List[Dict[str, Any]], res)
            res = await self.vector_storage.query(query, top_k=top_k)
            return cast(List[Dict[str, Any]], res)

        return []

    async def upsert(self, data: Dict[str, Dict[str, Any]]) -> None:
        """插入或更新文本塊到兩個存儲"""
        tasks = []

        if self.kv_storage and hasattr(self.kv_storage, "upsert"):
            tasks.append(self.kv_storage.upsert(data))

        if self.vector_storage and hasattr(self.vector_storage, "upsert"):
            tasks.append(self.vector_storage.upsert(data))

        if tasks:
            await asyncio.gather(*tasks)

    async def batch_get(self, chunk_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量獲取文本塊"""
        results = {}
        tasks = [self.get_by_id(cid) for cid in chunk_ids]
        chunks = await asyncio.gather(*tasks, return_exceptions=True)

        for cid, chunk in zip(chunk_ids, chunks):
            if isinstance(chunk, dict):
                results[cid] = chunk

        return results


@dataclass
class VectorStoreCollection:
    """
    向量庫集合

    管理 HGMem 需要的三個向量庫
    """

    entities: Optional[VectorStoreAdapter] = None
    relationships: Optional[VectorStoreAdapter] = None
    text_chunks: Optional[TextChunksAdapter] = None

    @classmethod
    def from_lightrag(cls, rag_instance: Any) -> "VectorStoreCollection":
        """
        從 LightRAG 實例創建向量庫集合

        Args:
            rag_instance: LightRAG 或 MyRAG 實例

        Returns:
            VectorStoreCollection 實例
        """
        entities = None
        relationships = None
        text_chunks = None

        # 獲取實體向量庫
        if hasattr(rag_instance, "entities_vdb") and rag_instance.entities_vdb:
            entities = VectorStoreAdapter(
                vector_storage=rag_instance.entities_vdb, namespace="entities"
            )

        # 獲取關係向量庫
        if hasattr(rag_instance, "relationships_vdb") and rag_instance.relationships_vdb:
            relationships = VectorStoreAdapter(
                vector_storage=rag_instance.relationships_vdb, namespace="relationships"
            )

        # 獲取文本塊存儲
        kv = getattr(rag_instance, "text_chunks", None)
        vdb = getattr(rag_instance, "text_chunks_vdb", None)
        if kv or vdb:
            text_chunks = TextChunksAdapter(kv_storage=kv, vector_storage=vdb)

        return cls(entities=entities, relationships=relationships, text_chunks=text_chunks)

    def is_complete(self) -> bool:
        """檢查是否所有向量庫都已配置"""
        return all(
            [
                self.entities is not None,
                self.relationships is not None,
                self.text_chunks is not None,
            ]
        )

    def get_status(self) -> Dict[str, bool]:
        """獲取各向量庫狀態"""
        return {
            "entities_vdb": self.entities is not None,
            "relationships_vdb": self.relationships is not None,
            "text_chunks_db": self.text_chunks is not None,
        }


# ============ In-Memory 實現 (用於測試) ============


@dataclass
class InMemoryVectorStore:
    """
    In-Memory Vector Store

    簡單的內存向量存儲，用於測試
    注意：不做真正的向量相似度計算，只做字符串匹配
    """

    _data: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    async def query(
        self, query: str, top_k: int = 10, filter_lambda: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """簡單的字符串匹配查詢"""
        results = []
        query_lower = query.lower()

        for id_, item in self._data.items():
            # 應用過濾器
            if filter_lambda:
                item_with_id = {**item, "__id__": id_}
                if not filter_lambda(item_with_id):
                    continue

            # 簡單的字符串匹配 (生產環境應使用真正的向量相似度)
            content = item.get("content", "").lower()
            if query_lower in content or any(word in content for word in query_lower.split()):
                results.append({"id": id_, **item, "distance": 0.5})
            else:
                results.append({"id": id_, **item, "distance": 0.9})

        # 按距離排序
        results.sort(key=lambda x: x["distance"])
        return results[:top_k]

    async def upsert(self, data: Dict[str, Dict[str, Any]]) -> None:
        """插入或更新"""
        self._data.update(data)

    async def delete(self, ids: List[str]) -> None:
        """刪除"""
        for id_ in ids:
            self._data.pop(id_, None)

    async def get_by_id(self, id_: str) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取"""
        return self._data.get(id_)

    async def get_by_ids(self, ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量獲取"""
        return {id_: self._data[id_] for id_ in ids if id_ in self._data}
