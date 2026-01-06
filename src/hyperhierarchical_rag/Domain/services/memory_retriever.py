"""
Memory Pointwise Related Info Service

基於記憶點檢索相關的 text chunks。
這是 HGMem 中 get_memory_pointwise_related_info() 的實現。

核心邏輯：
1. 對每個記憶點，獲取 inner chunks (直接相關的 source chunks)
2. 對每個記憶點，獲取 outer chunks (鄰居節點的 source chunks)
3. 使用向量相似度排序並截斷
4. 返回格式化的上下文
"""

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import asyncio


# ============ 輔助函數 ============

def split_string_by_multi_markers(content: str, markers: List[str]) -> List[str]:
    """根據標記分割字符串"""
    import re
    pattern = "|".join(re.escape(m) for m in markers)
    return [s.strip() for s in re.split(pattern, content) if s.strip()]


def truncate_attribute_by_token_size(
    items: List[Dict], 
    attribute: str, 
    max_token_size: int,
    encoding_name: str = "cl100k_base"
) -> None:
    """截斷屬性到指定 token 大小 (原地修改)"""
    try:
        import tiktoken
        enc = tiktoken.get_encoding(encoding_name)
        
        for item in items:
            if attribute in item and item[attribute]:
                text = item[attribute]
                tokens = enc.encode(text)
                if len(tokens) > max_token_size:
                    item[attribute] = enc.decode(tokens[:max_token_size]) + "..."
    except ImportError:
        # 沒有 tiktoken，使用字符估算
        for item in items:
            if attribute in item and item[attribute]:
                text = item[attribute]
                char_limit = max_token_size * 4  # 粗略估算
                if len(text) > char_limit:
                    item[attribute] = text[:char_limit] + "..."


def truncate_list_by_token_size(
    items: List[Any],
    key: Callable[[Any], str],
    max_token_size: int,
    encoding_name: str = "cl100k_base"
) -> List[Any]:
    """截斷列表到指定 token 大小"""
    try:
        import tiktoken
        enc = tiktoken.get_encoding(encoding_name)
        
        result = []
        total_tokens = 0
        
        for item in items:
            text = key(item)
            item_tokens = len(enc.encode(text))
            if total_tokens + item_tokens > max_token_size:
                break
            result.append(item)
            total_tokens += item_tokens
        
        return result
    except ImportError:
        # Fallback
        char_limit = max_token_size * 4
        result = []
        total_chars = 0
        
        for item in items:
            text = key(item)
            if total_chars + len(text) > char_limit:
                break
            result.append(item)
            total_chars += len(text)
        
        return result


def build_entities_context(entities_data: List[Dict]) -> str:
    """構建實體上下文 CSV"""
    if not entities_data:
        return ""
    
    lines = ["entity_name,entity_type,description"]
    for entity in entities_data:
        name = entity.get("entity_name", "")
        etype = entity.get("entity_type", "")
        desc = entity.get("description", "").replace(",", ";").replace("\n", " ")
        lines.append(f"{name},{etype},{desc}")
    
    return "\n".join(lines)


def build_text_chunks_context(chunks: List[Dict]) -> str:
    """構建文本塊上下文"""
    if not chunks:
        return ""
    
    lines = []
    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "")
        doc_id = chunk.get("full_doc_id", "unknown")
        lines.append(f"[Chunk {i+1}] (Doc: {doc_id})\n{content}")
    
    return "\n\n".join(lines)


# ============ 查詢參數 ============

@dataclass
class MemoryQueryParam:
    """記憶點查詢參數"""
    
    # Inner chunks (直接相關)
    max_inner_chunks_per_memory_point: int = 3
    
    # Outer chunks (鄰居相關)
    max_outer_chunks_per_memory_point: int = 2
    
    # 總體限制
    max_text_chunks: int = 20
    max_token_for_final_text_chunks: int = 4000
    max_token_for_entity_description: int = 200


# ============ 核心服務 ============

@dataclass
class MemoryPointwiseRetriever:
    """
    基於記憶點的檢索服務
    
    實現 HGMem 的 get_memory_pointwise_related_info() 功能
    
    Usage:
        retriever = MemoryPointwiseRetriever(
            kg_adapter=kg_adapter,
            text_chunks_adapter=text_chunks_adapter
        )
        
        result = await retriever.get_memory_pointwise_related_info(
            memory_points=[["ENTITY_A", "ENTITY_B"], ["ENTITY_C"]],
            query="some query...",
            query_param=MemoryQueryParam()
        )
    """
    
    kg_adapter: Any  # LightRAGKGAdapter
    text_chunks_adapter: Any  # TextChunksAdapter
    
    # Graph field separator (HGMem 使用 <SEP>)
    graph_field_sep: str = "<SEP>"
    
    async def get_memory_pointwise_related_info(
        self,
        memory_points: List[List[str]],
        query: str,
        query_param: MemoryQueryParam = None,
        history_retrieved_objects: Optional[List[Dict]] = None,
        memory_hypergraph: Any = None,
        verbose: bool = True
    ) -> Tuple[str, List[Dict], List[str]] | str:
        """
        基於記憶點檢索相關的 text chunks
        
        Args:
            memory_points: 記憶點列表，每個記憶點是實體名稱列表
            query: 查詢文本
            query_param: 查詢參數
            history_retrieved_objects: 歷史檢索對象 (用於過濾已檢索的 chunks)
            memory_hypergraph: 記憶超圖 (用於獲取記憶點描述)
            verbose: 是否返回詳細信息
            
        Returns:
            如果 verbose=True: (context_str, pointwise_chunks, final_chunk_ids)
            如果 verbose=False: context_str
        """
        if query_param is None:
            query_param = MemoryQueryParam()
        
        # 獲取歷史檢索的 chunk IDs
        history_chunk_ids = self._extract_history_chunk_ids(history_retrieved_objects)
        
        # 1. 收集記憶點相關的實體數據
        related_entities_data, related_entities_dict = await self._collect_related_entities(
            memory_points, query_param
        )
        
        # 2. 對每個記憶點檢索 chunks
        pointwise_chunks, final_chunk_ids = await self._retrieve_chunks_per_memory_point(
            memory_points=memory_points,
            query=query,
            query_param=query_param,
            related_entities_dict=related_entities_dict,
            history_chunk_ids=history_chunk_ids,
            memory_hypergraph=memory_hypergraph
        )
        
        # 3. 如果超過限制，重新排序並截斷
        if len(final_chunk_ids) > query_param.max_text_chunks:
            final_chunk_ids = await self._rerank_and_truncate(
                final_chunk_ids, query, query_param.max_text_chunks
            )
        
        # 4. 獲取最終的 chunk 內容
        all_text_chunks = await self._fetch_and_format_chunks(
            final_chunk_ids, query_param.max_token_for_final_text_chunks
        )
        
        # 5. 構建上下文
        entities_context = build_entities_context(related_entities_data)
        text_chunks_context = build_text_chunks_context(all_text_chunks)
        
        memory_related_info = f"""-----Entities-----
```csv
{entities_context}
```

-----Sources-----
```csv
{text_chunks_context}
```
"""
        
        if verbose:
            return memory_related_info, pointwise_chunks, list(final_chunk_ids)
        return memory_related_info
    
    def _extract_history_chunk_ids(
        self, 
        history_retrieved_objects: Optional[List[Dict]]
    ) -> Set[str]:
        """提取歷史檢索的 chunk IDs"""
        if not history_retrieved_objects:
            return set()
        
        chunk_ids = set()
        for obj in history_retrieved_objects:
            if "text_chunks_ids" in obj:
                for chunk_list in obj["text_chunks_ids"]:
                    if isinstance(chunk_list, list):
                        chunk_ids.update(chunk_list)
                    else:
                        chunk_ids.add(chunk_list)
        
        return chunk_ids
    
    async def _collect_related_entities(
        self,
        memory_points: List[List[str]],
        query_param: MemoryQueryParam
    ) -> Tuple[List[Dict], Dict[str, Dict]]:
        """收集記憶點相關的所有實體數據"""
        related_entities_data = []
        related_entities_dict = {}
        
        for mp in memory_points:
            for entity_name in mp:
                if entity_name not in related_entities_dict:
                    node = await self.kg_adapter.get_node(entity_name)
                    if node:
                        node_data = {"entity_name": entity_name, **node}
                        related_entities_data.append(node_data)
                        related_entities_dict[entity_name] = node_data
        
        # 截斷描述
        truncate_attribute_by_token_size(
            related_entities_data, 
            "description", 
            query_param.max_token_for_entity_description
        )
        
        return related_entities_data, related_entities_dict
    
    async def _retrieve_chunks_per_memory_point(
        self,
        memory_points: List[List[str]],
        query: str,
        query_param: MemoryQueryParam,
        related_entities_dict: Dict[str, Dict],
        history_chunk_ids: Set[str],
        memory_hypergraph: Any
    ) -> Tuple[List[Dict], Set[str]]:
        """對每個記憶點檢索相關 chunks"""
        pointwise_chunks = []
        final_chunk_ids = set()
        
        for mp in memory_points:
            if not mp:
                continue
            
            # 獲取記憶點描述 (用於查詢)
            mp_info = await self._get_memory_point_info(mp, memory_hypergraph)
            
            # Inner chunks: 記憶點實體直接關聯的 chunks
            inner_chunk_ids = await self._get_inner_chunks(
                mp, related_entities_dict, history_chunk_ids
            )
            selected_inner = await self._select_chunks_by_similarity(
                inner_chunk_ids, 
                mp_info or query,
                query_param.max_inner_chunks_per_memory_point
            )
            final_chunk_ids.update(selected_inner)
            
            # Outer chunks: 鄰居節點關聯的 chunks
            outer_chunk_ids = await self._get_outer_chunks(
                mp, related_entities_dict, selected_inner, history_chunk_ids
            )
            selected_outer = await self._select_chunks_by_similarity(
                outer_chunk_ids,
                mp_info or query,
                query_param.max_outer_chunks_per_memory_point
            )
            final_chunk_ids.update(selected_outer)
            
            pointwise_chunks.append({
                "inner_chunks": list(selected_inner),
                "outer_chunks": list(selected_outer)
            })
        
        return pointwise_chunks, final_chunk_ids
    
    async def _get_memory_point_info(
        self, 
        mp: List[str], 
        memory_hypergraph: Any
    ) -> Optional[str]:
        """獲取記憶點的描述信息"""
        if memory_hypergraph and hasattr(memory_hypergraph, 'get_hyperedge'):
            try:
                mp_tuple = tuple(mp) if isinstance(mp, list) else mp
                edge_data = await memory_hypergraph.get_hyperedge(mp_tuple)
                if edge_data:
                    return edge_data.get('description', '')
            except Exception:
                pass
        return None
    
    async def _get_inner_chunks(
        self,
        mp: List[str],
        related_entities_dict: Dict[str, Dict],
        history_chunk_ids: Set[str]
    ) -> Set[str]:
        """獲取記憶點的 inner chunks (直接相關)"""
        chunk_ids = set()
        
        for entity_name in mp:
            node_data = related_entities_dict.get(entity_name)
            if not node_data or not node_data.get("source_id"):
                continue
            
            source_ids = set(split_string_by_multi_markers(
                str(node_data["source_id"]), [self.graph_field_sep]
            ))
            chunk_ids.update(source_ids)
        
        # 過濾：只保留歷史檢索過的 (如果有歷史)
        if history_chunk_ids:
            chunk_ids = chunk_ids & history_chunk_ids
        
        # 驗證 chunks 存在
        valid_chunks = set()
        for cid in chunk_ids:
            if await self.text_chunks_adapter.get_by_id(cid):
                valid_chunks.add(cid)
        
        return valid_chunks
    
    async def _get_outer_chunks(
        self,
        mp: List[str],
        related_entities_dict: Dict[str, Dict],
        exclude_ids: Set[str],
        history_chunk_ids: Set[str]
    ) -> Set[str]:
        """獲取記憶點的 outer chunks (鄰居相關)"""
        chunk_ids = set()
        
        for entity_name in mp:
            neighbors = await self.kg_adapter.get_neighbor_nodes(entity_name)
            
            for neighbor in neighbors:
                if neighbor in related_entities_dict:
                    continue  # 跳過已在記憶點中的實體
                
                neighbor_data = await self.kg_adapter.get_node(neighbor)
                if neighbor_data and neighbor_data.get("source_id"):
                    source_ids = set(split_string_by_multi_markers(
                        str(neighbor_data["source_id"]), [self.graph_field_sep]
                    ))
                    chunk_ids.update(source_ids)
        
        # 排除 inner chunks
        chunk_ids -= exclude_ids
        
        # 過濾：只保留歷史檢索過的 (如果有歷史)
        if history_chunk_ids:
            chunk_ids = chunk_ids & history_chunk_ids
        
        # 驗證 chunks 存在
        valid_chunks = set()
        for cid in chunk_ids:
            if await self.text_chunks_adapter.get_by_id(cid):
                valid_chunks.add(cid)
        
        return valid_chunks
    
    async def _select_chunks_by_similarity(
        self,
        chunk_ids: Set[str],
        query: str,
        top_k: int
    ) -> Set[str]:
        """使用向量相似度選擇 top-k chunks"""
        if not chunk_ids or top_k <= 0:
            return set()
        
        if len(chunk_ids) <= top_k:
            return chunk_ids
        
        # 使用向量查詢排序
        filter_lambda = lambda data: data.get("__id__") in chunk_ids or data.get("id") in chunk_ids
        
        try:
            results = await self.text_chunks_adapter.query(
                query, top_k=top_k, filter_lambda=filter_lambda
            )
            return {r.get("id", r.get("__id__")) for r in results if r}
        except Exception:
            # Fallback: 直接返回前 top_k 個
            return set(list(chunk_ids)[:top_k])
    
    async def _rerank_and_truncate(
        self,
        chunk_ids: Set[str],
        query: str,
        max_chunks: int
    ) -> Set[str]:
        """重新排序並截斷到 max_chunks"""
        filter_lambda = lambda data: data.get("__id__") in chunk_ids or data.get("id") in chunk_ids
        
        try:
            results = await self.text_chunks_adapter.query(
                query, top_k=max_chunks, filter_lambda=filter_lambda
            )
            return {r.get("id", r.get("__id__")) for r in results if r}
        except Exception:
            return set(list(chunk_ids)[:max_chunks])
    
    async def _fetch_and_format_chunks(
        self,
        chunk_ids: Set[str],
        max_token_size: int
    ) -> List[Dict]:
        """獲取並格式化 chunks"""
        if not chunk_ids:
            return []
        
        # 批量獲取
        tasks = [self.text_chunks_adapter.get_by_id(cid) for cid in chunk_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_chunks = []
        for cid, data in zip(chunk_ids, results):
            if isinstance(data, dict) and "content" in data:
                valid_chunks.append({"id": cid, "data": data})
        
        # 按文檔和順序排序
        valid_chunks.sort(key=lambda x: (
            x["data"].get("full_doc_id", ""),
            x["data"].get("chunk_order_index", 0)
        ))
        
        # 截斷
        truncated = truncate_list_by_token_size(
            valid_chunks,
            key=lambda x: x["data"]["content"],
            max_token_size=max_token_size
        )
        
        return [t["data"] for t in truncated]


# ============ 便捷函數 ============

async def get_memory_pointwise_related_info(
    memory_points: List[List[str]],
    knowledge_graph_inst: Any,
    text_chunks_db: Any,
    text_chunks_vdb: Any,
    query: str,
    query_param: Any,
    history_retrieved_objects: Optional[List[Dict]] = None,
    memory_hypergraph: Any = None,
    verbose: bool = True
):
    """
    獨立函數版本 (兼容 HGMem 原始介面)
    """
    from .vector_store_adapter import TextChunksAdapter
    
    text_chunks_adapter = TextChunksAdapter(
        kv_storage=text_chunks_db,
        vector_storage=text_chunks_vdb
    )
    
    retriever = MemoryPointwiseRetriever(
        kg_adapter=knowledge_graph_inst,
        text_chunks_adapter=text_chunks_adapter
    )
    
    # 轉換查詢參數
    mp_param = MemoryQueryParam(
        max_inner_chunks_per_memory_point=getattr(query_param, 'max_inner_chunks_per_memory_point', 3),
        max_outer_chunks_per_memory_point=getattr(query_param, 'max_outer_chunks_per_memory_point', 2),
        max_text_chunks=getattr(query_param, 'max_text_chunks', 20),
        max_token_for_final_text_chunks=getattr(query_param, 'max_token_for_final_text_chunks', 4000),
        max_token_for_entity_description=getattr(query_param, 'max_token_for_entity_description', 200)
    )
    
    return await retriever.get_memory_pointwise_related_info(
        memory_points=memory_points,
        query=query,
        query_param=mp_param,
        history_retrieved_objects=history_retrieved_objects,
        memory_hypergraph=memory_hypergraph,
        verbose=verbose
    )
