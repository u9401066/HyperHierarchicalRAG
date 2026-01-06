"""
KG-Memory 雙向同步服務

當記憶點引用不存在於 Knowledge Graph 的實體時，
自動從檢索到的上下文中提取實體和關係，補全到 KG。

這是 HGMem 最核心的創新之一：
- Memory 演化時發現缺失實體
- 從對話/檢索上下文中提取這些實體的描述
- 自動補全到 Knowledge Graph 和 Vector Store
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import re
import hashlib


# ============ 輔助函數 ============

def compute_mdhash_id(content: str, prefix: str = "") -> str:
    """計算 MD5 hash ID"""
    return prefix + hashlib.md5(content.encode()).hexdigest()


def clean_str(s: str) -> str:
    """清理字符串"""
    return s.strip().strip('"').strip("'")


def split_string_by_multi_markers(content: str, markers: List[str]) -> List[str]:
    """根據多個標記分割字符串"""
    pattern = "|".join(re.escape(m) for m in markers)
    return [s.strip() for s in re.split(pattern, content) if s.strip()]


# ============ Prompts ============

SUMMARIZE_ABSENT_ENTITIES_PROMPT = """---Goal---
Given the following context information and target entities/relationships, 
summarize the descriptions for the entities and relationships that appear in the context.

---Target Entities---
{target_entities}

---Target Relationships---
{target_relationships}

---Context Information---
{info}

---Output Format---
For each entity, output: (entity{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<description>){record_delimiter}
For each relationship, output: (relationship{tuple_delimiter}<source>{tuple_delimiter}<target>{tuple_delimiter}<description>{tuple_delimiter}<keywords>){record_delimiter}

If an entity/relationship cannot be found in the context, skip it.

{completion_delimiter}
"""


# ============ 後處理函數 ============

def postprocess_summarize_absent_entities_relationships(
    response: str, 
    format_dict: Dict[str, str]
) -> Tuple[Dict[str, Dict], Dict[tuple, Dict]]:
    """
    解析 LLM 對缺失實體/關係的摘要回應
    
    Returns:
        (entities_dict, relationships_dict)
    """
    tuple_delimiter = format_dict.get("tuple_delimiter", "|")
    record_delimiter = format_dict.get("record_delimiter", "\n")
    completion_delimiter = format_dict.get("completion_delimiter", "<END>")
    
    response = response.strip()
    records = split_string_by_multi_markers(response, [record_delimiter, completion_delimiter])
    
    entities = {}
    relationships = {}
    
    for record in records:
        match = re.search(r"\((.*)\)", record)
        if not match:
            continue
        
        content = match.group(1)
        attributes = split_string_by_multi_markers(content, [tuple_delimiter])
        
        if len(attributes) >= 4 and attributes[0].lower() == 'entity':
            entity_name = clean_str(attributes[1].upper())
            if entity_name:
                entities[entity_name] = {
                    "entity_name": entity_name,
                    "entity_type": clean_str(attributes[2].upper()),
                    "description": clean_str(attributes[3]),
                    "source_id": "",
                    "state": "temporary"
                }
        
        elif len(attributes) >= 5 and attributes[0].lower() == 'relationship':
            source = clean_str(attributes[1].upper())
            target = clean_str(attributes[2].upper())
            if source and target:
                relationships[(source, target)] = {
                    "src_id": source,
                    "tgt_id": target,
                    "description": clean_str(attributes[3]),
                    "keywords": clean_str(attributes[4]) if len(attributes) > 4 else "",
                    "source_id": "",
                    "state": "temporary"
                }
    
    return entities, relationships


# ============ 核心功能 ============

@dataclass
class KGMemorySyncService:
    """
    KG-Memory 雙向同步服務
    
    Usage:
        sync_service = KGMemorySyncService(
            kg_adapter=kg_adapter,
            entities_vdb=entities_adapter,
            relationships_vdb=relationships_adapter,
            llm_func=llm_func
        )
        
        # 當演化發現缺失實體時
        await sync_service.collect_absent_entities_relationships(
            absent_entities_hyperedges_kv={"ENTITY_A": [["ENTITY_A", "ENTITY_B"]]},
            context_info="some retrieved context..."
        )
    """
    
    kg_adapter: Any  # LightRAGKGAdapter
    entities_vdb: Any  # VectorStoreAdapter
    relationships_vdb: Any  # VectorStoreAdapter
    llm_func: Callable  # LLM 函數
    
    # 格式設定
    format_dict: Dict[str, str] = None
    
    # 描述函數 (用於生成向量內容)
    entity_description_func: Callable = None
    relationship_description_func: Callable = None
    
    def __post_init__(self):
        if self.format_dict is None:
            self.format_dict = {
                "language": "English",
                "entity_types": "PERSON, ORGANIZATION, LOCATION, EVENT, CONCEPT",
                "tuple_delimiter": "|",
                "record_delimiter": "\n",
                "object_delimiter": ", ",
                "completion_delimiter": "<END>"
            }
        
        if self.entity_description_func is None:
            self.entity_description_func = lambda name, desc: f"{name}: {desc}"
        
        if self.relationship_description_func is None:
            self.relationship_description_func = lambda kw, src, tgt, desc: f"{src} -> {tgt} ({kw}): {desc}"
    
    async def collect_absent_entities_relationships(
        self,
        absent_entities_hyperedges_kv: Dict[str, List[List[str]]],
        context_info: str,
        max_iterations: int = 3
    ) -> Tuple[Dict[str, Dict], Dict[tuple, Dict]]:
        """
        收集並補全缺失的實體和關係
        
        這是 HGMem 的核心功能：當記憶點引用了 KG 中不存在的實體時，
        從上下文中提取這些實體的信息並補全到 KG。
        
        Args:
            absent_entities_hyperedges_kv: {entity_name: [[hyperedge1], [hyperedge2]...]}
                缺失實體及其相關的超邊
            context_info: 檢索到的上下文信息
            max_iterations: 最大迭代次數
            
        Returns:
            (collected_entities, collected_relationships)
        """
        if not absent_entities_hyperedges_kv:
            return {}, {}
        
        # 構建需要查找的唯一關係
        absent_relationships = self._build_absent_relationships(absent_entities_hyperedges_kv)
        
        collected_entities = {}
        collected_relationships = {}
        remaining_entities = list(absent_entities_hyperedges_kv.keys())
        remaining_relationships = list(absent_relationships)
        
        for iteration in range(max_iterations):
            if not remaining_entities and not remaining_relationships:
                break
            
            # 構建 prompt
            prompt = self._build_summarize_prompt(
                remaining_entities, 
                remaining_relationships, 
                context_info
            )
            
            # 調用 LLM
            response = await self.llm_func(prompt)
            
            # 解析結果
            new_entities, new_relationships = postprocess_summarize_absent_entities_relationships(
                response, self.format_dict
            )
            
            # 只保留目標中的實體和關係
            valid_entities = {
                k: v for k, v in new_entities.items() 
                if k in absent_entities_hyperedges_kv
            }
            valid_relationships = {
                k: v for k, v in new_relationships.items()
                if k in absent_relationships
            }
            
            collected_entities.update(valid_entities)
            collected_relationships.update(valid_relationships)
            
            # 更新剩餘列表
            remaining_entities = [
                e for e in absent_entities_hyperedges_kv.keys()
                if e not in collected_entities
            ]
            remaining_relationships = [
                r for r in absent_relationships
                if r not in collected_relationships
            ]
        
        # 將收集到的實體和關係寫入 KG 和向量庫
        await self._add_entities_to_kg_and_vdb(
            collected_entities, remaining_entities
        )
        await self._add_relationships_to_kg_and_vdb(
            collected_relationships, remaining_relationships
        )
        
        return collected_entities, collected_relationships
    
    def _build_absent_relationships(
        self, 
        absent_entities_hyperedges_kv: Dict[str, List[List[str]]]
    ) -> List[Tuple[str, str]]:
        """構建缺失關係列表"""
        relationships = []
        
        for entity, hyperedges in absent_entities_hyperedges_kv.items():
            for hyperedge in hyperedges:
                for related_entity in hyperedge:
                    if entity != related_entity:
                        pair = tuple(sorted([entity, related_entity]))
                        if pair not in relationships:
                            relationships.append(pair)
        
        return relationships
    
    def _build_summarize_prompt(
        self,
        target_entities: List[str],
        target_relationships: List[Tuple[str, str]],
        context_info: str
    ) -> str:
        """構建 LLM prompt"""
        entities_str = "\n".join(f"- {e}" for e in target_entities) if target_entities else "<None>"
        relationships_str = "\n".join(
            f"- {r[0]} --&-- {r[1]}" for r in target_relationships
        ) if target_relationships else "<None>"
        
        return SUMMARIZE_ABSENT_ENTITIES_PROMPT.format(
            target_entities=entities_str,
            target_relationships=relationships_str,
            info=context_info,
            **self.format_dict
        )
    
    async def _add_entities_to_kg_and_vdb(
        self,
        collected_entities: Dict[str, Dict],
        remaining_entities: List[str]
    ) -> None:
        """將實體添加到 KG 和向量庫"""
        data_for_vdb = {}
        
        # 已收集的實體 (有描述)
        for entity_name, entity_info in collected_entities.items():
            await self.kg_adapter.upsert_node(entity_name, entity_info)
            
            key = compute_mdhash_id(entity_name, prefix="ent-")
            data_for_vdb[key] = {
                "content": self.entity_description_func(
                    entity_name, entity_info.get("description", "")
                ),
                "entity_name": entity_name
            }
        
        # 剩餘實體 (標記為 missing)
        for entity_name in remaining_entities:
            entity_info = {
                "entity_name": entity_name,
                "entity_type": "",
                "description": "",
                "source_id": "",
                "state": "missing"
            }
            await self.kg_adapter.upsert_node(entity_name, entity_info)
            
            key = compute_mdhash_id(entity_name, prefix="ent-")
            data_for_vdb[key] = {
                "content": self.entity_description_func(entity_name, ""),
                "entity_name": entity_name
            }
        
        # 批量寫入向量庫
        if data_for_vdb and self.entities_vdb:
            await self.entities_vdb.upsert(data_for_vdb)
    
    async def _add_relationships_to_kg_and_vdb(
        self,
        collected_relationships: Dict[tuple, Dict],
        remaining_relationships: List[Tuple[str, str]]
    ) -> None:
        """將關係添加到 KG 和向量庫"""
        data_for_vdb = {}
        
        # 已收集的關係 (有描述)
        for (src, tgt), rel_info in collected_relationships.items():
            edge_data = {
                "description": rel_info.get("description", ""),
                "keywords": rel_info.get("keywords", ""),
                "source_id": rel_info.get("source_id", ""),
                "state": "temporary"
            }
            await self.kg_adapter.upsert_edge(src, tgt, edge_data)
            
            key = compute_mdhash_id(src + tgt, prefix="rel-")
            data_for_vdb[key] = {
                "src_id": src,
                "tgt_id": tgt,
                "content": self.relationship_description_func(
                    rel_info.get("keywords", ""),
                    src, tgt,
                    rel_info.get("description", "")
                )
            }
        
        # 剩餘關係 (標記為 missing)
        for (src, tgt) in remaining_relationships:
            edge_data = {
                "description": "",
                "keywords": "",
                "source_id": "",
                "state": "missing"
            }
            await self.kg_adapter.upsert_edge(src, tgt, edge_data)
            
            key = compute_mdhash_id(src + tgt, prefix="rel-")
            data_for_vdb[key] = {
                "src_id": src,
                "tgt_id": tgt,
                "content": self.relationship_description_func("", src, tgt, "")
            }
        
        # 批量寫入向量庫
        if data_for_vdb and self.relationships_vdb:
            await self.relationships_vdb.upsert(data_for_vdb)


# ============ 便捷函數 ============

async def collect_absent_entities_relationships(
    absent_entities_hyperedges_kv: Dict[str, List[List[str]]],
    info: str,
    knowledge_graph_inst: Any,
    entities_vdb: Any,
    relationships_vdb: Any,
    llm_model_func: Callable,
    format_dict: Dict[str, str],
    entity_description_func: Callable,
    relationship_description_func: Callable
) -> Tuple[Dict, Dict]:
    """
    獨立函數版本 (兼容 HGMem 原始介面)
    
    這是 HGMem memory.py 中 collect_absent_entities_relationships() 的等價實現
    """
    service = KGMemorySyncService(
        kg_adapter=knowledge_graph_inst,
        entities_vdb=entities_vdb,
        relationships_vdb=relationships_vdb,
        llm_func=llm_model_func,
        format_dict=format_dict,
        entity_description_func=entity_description_func,
        relationship_description_func=relationship_description_func
    )
    
    return await service.collect_absent_entities_relationships(
        absent_entities_hyperedges_kv=absent_entities_hyperedges_kv,
        context_info=info
    )
