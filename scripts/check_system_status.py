#!/usr/bin/env python3
"""
檢查系統狀態：Hypergraph、可視化、持續更新機制
"""

import asyncio

from hyperhierarchical_rag import RAGEngine


async def check_system_status() -> None:
    """檢查系統完整狀態"""

    print("=" * 70)
    print("🔍 系統狀態檢查")
    print("=" * 70)

    engine = RAGEngine.from_env()
    status = await engine.initialize()

    print(f"\n📦 初始化狀態: {status['status']}")
    for comp, state in status.get("components", {}).items():
        icon = "✅" if state == "ok" else "❌"
        print(f"   {icon} {comp}: {state}")

    # ========== 1. Graph 統計 ==========
    print("\n" + "=" * 70)
    print("📊 Knowledge Graph 統計")
    print("=" * 70)

    stats = engine.get_graph_stats()
    print(f"   LightRAG KG: {stats.get('lightrag_kg', {})}")
    print(f"   HGMem Hypergraph: {stats.get('hgmem_hypergraph', {})}")
    print(f"   Memory Points: {stats.get('memory_evolution', {}).get('memory_points', 0)}")
    print(f"   總實體數: {stats.get('total_entities', 0)}")
    print(f"   總關係數: {stats.get('total_relations', 0)}")

    # ========== 2. 測試可視化生成 ==========
    print("\n" + "=" * 70)
    print("🎨 測試可視化生成")
    print("=" * 70)

    viz_result = await engine.generate_visualization(
        filename="test_knowledge_graph.html", title="Test Knowledge Graph Visualization"
    )

    if "error" in viz_result:
        print(f"   ❌ 錯誤: {viz_result['error']}")
    else:
        print(f"   ✅ HTML: {viz_result.get('html')}")
        print(f"   ✅ JSON: {viz_result.get('json')}")
        print(f"   節點數: {viz_result.get('nodes_count')}")
        print(f"   邊數: {viz_result.get('edges_count')}")

    # ========== 3. 測試增量插入 ==========
    print("\n" + "=" * 70)
    print("📝 測試增量插入")
    print("=" * 70)

    test_doc = """
    GraphRAG is a new approach that combines knowledge graphs with retrieval-augmented generation.
    It was developed by Microsoft Research to improve question-answering capabilities.
    The key innovation is using community detection algorithms on the knowledge graph.
    """

    result = await engine.insert(test_doc, doc_id="test_graphrag_doc")
    print(f"   插入結果: {result}")

    # 檢查插入後的統計
    new_stats = engine.get_graph_stats()
    print(f"   插入後 LightRAG KG: {new_stats.get('lightrag_kg', {})}")

    # ========== 4. 重新生成可視化 ==========
    print("\n" + "=" * 70)
    print("🔄 插入後重新生成可視化")
    print("=" * 70)

    viz_result2 = await engine.generate_visualization(
        filename="updated_knowledge_graph.html", title="Updated Knowledge Graph"
    )

    if "error" not in viz_result2:
        print(f"   ✅ 更新後節點數: {viz_result2.get('nodes_count')}")
        print(f"   ✅ 更新後邊數: {viz_result2.get('edges_count')}")
        print(f"   檔案: {viz_result2.get('html')}")

    print("\n" + "=" * 70)
    print("✨ 測試完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(check_system_status())
