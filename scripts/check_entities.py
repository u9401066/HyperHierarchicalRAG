#!/usr/bin/env python3
"""檢查知識圖譜中的實體"""

import asyncio
from hyperhierarchical_rag import RAGEngine


async def check() -> None:
    engine = RAGEngine.from_env()
    await engine.initialize()
    
    # 1. 檢查統計
    stats = engine.get_graph_stats()
    print("=" * 60)
    print("Knowledge Graph 統計")
    print("=" * 60)
    print(f"LightRAG KG: {stats['lightrag_kg']}")
    print(f"HGMem Hypergraph: {stats['hgmem_hypergraph']}")
    
    # 2. 列出實體
    graph = engine._lightrag.chunk_entity_relation_graph._graph
    entities = list(graph.nodes())
    
    print(f"\n總共 {len(entities)} 個實體:")
    print("-" * 60)
    
    # 按字母排序顯示
    for e in sorted(entities)[:30]:
        print(f"  • {e}")
    
    if len(entities) > 30:
        print(f"  ... 還有 {len(entities) - 30} 個")
    
    # 3. 檢查是否包含 arXiv 論文相關實體
    print("\n" + "=" * 60)
    print("arXiv 論文相關實體檢查")
    print("=" * 60)
    
    keywords = ["RAG", "EVOR", "AR-RAG", "RETRIEVAL", "QURANIC", "MEMBERSHIP"]
    for kw in keywords:
        matches = [e for e in entities if kw.upper() in e.upper()]
        if matches:
            print(f"\n'{kw}' 相關:")
            for m in matches[:5]:
                print(f"  ✓ {m}")


if __name__ == "__main__":
    asyncio.run(check())
