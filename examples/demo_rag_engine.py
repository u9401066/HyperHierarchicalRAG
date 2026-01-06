"""
HyperHierarchicalRAG 使用範例

展示如何：
1. 初始化 RAG Engine
2. 插入文檔
3. 執行查詢
4. 生成可視化

執行方式：
    # 確保已設定 OPENAI_API_KEY
    export OPENAI_API_KEY=sk-your-key
    
    # 或使用 .env 檔案
    cp .env.example .env
    # 編輯 .env 填入 API Key
    
    # 執行範例
    python examples/demo_rag_engine.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hyperhierarchical_rag.engine import RAGEngine
from hyperhierarchical_rag.Domain.entities import HyperNode, HyperEdge, NodeLevel


async def main():
    print("=" * 70)
    print("HyperHierarchicalRAG Demo")
    print("=" * 70)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  OPENAI_API_KEY not set!")
        print("   Set it with: export OPENAI_API_KEY=sk-your-key")
        print("   Or create a .env file from .env.example")
        print("\n   Running in demo mode with mock data...\n")
        await run_demo_mode()
        return
    
    # Initialize RAG Engine
    print("\n🚀 Initializing RAG Engine...")
    engine = RAGEngine.from_env()
    
    try:
        status = await engine.initialize()
        print(f"   Status: {status['status']}")
        for component, state in status.get("components", {}).items():
            print(f"   - {component}: {state}")
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        print("   Running in demo mode...")
        await run_demo_mode()
        return
    
    # Insert sample documents
    print("\n📄 Inserting sample documents...")
    
    sample_docs = [
        """
        Propofol is a short-acting intravenous anesthetic agent used for induction and 
        maintenance of general anesthesia, sedation in ICU, and procedural sedation. 
        It has a rapid onset (30-45 seconds) and short duration. Common side effects 
        include respiratory depression and hypotension.
        """,
        """
        Remimazolam is a novel ultra-short-acting benzodiazepine for procedural sedation 
        and general anesthesia. Unlike propofol, it has a specific reversal agent (flumazenil). 
        Studies suggest lower incidence of respiratory depression and faster recovery compared 
        to propofol. It may reduce delirium incidence in ICU patients.
        """,
        """
        Delirium in ICU is a common complication affecting up to 80% of mechanically ventilated 
        patients. Risk factors include sedation depth, benzodiazepine use, and age. 
        Light sedation protocols and avoiding benzodiazepines (except remimazolam) may reduce 
        delirium incidence.
        """,
    ]
    
    for i, doc in enumerate(sample_docs, 1):
        result = await engine.insert(doc.strip(), doc_id=f"doc_{i}")
        print(f"   Doc {i}: {result.get('hypergraph', {}).get('status', 'unknown')}")
    
    # Show graph stats
    print("\n📊 Graph Statistics:")
    stats = engine.get_graph_stats()
    print(f"   Nodes: {stats['nodes']['total']} (LOCAL: {stats['nodes']['local']}, GLOBAL: {stats['nodes']['global']})")
    print(f"   Edges: {stats['edges']['total']} (binary: {stats['edges']['binary']}, n-ary: {stats['edges']['n_ary']})")
    print(f"   Cross-level edges: {stats['edges']['cross_level']}")
    
    # Execute queries
    print("\n🔍 Executing queries...")
    
    queries = [
        ("propofol dosage", "local"),
        ("sedation trends ICU", "global"),
        ("Compare propofol and remimazolam for delirium", "hybrid"),
    ]
    
    for query, mode in queries:
        print(f"\n   Query: \"{query}\" (mode={mode})")
        result = await engine.query(
            query=query,
            mode=mode,
            top_k=5,
            visualize=True,
        )
        
        hr = result.get("hypergraph_response", {})
        print(f"   - Keywords: LOCAL={hr.get('local_keywords', [])}, GLOBAL={hr.get('global_keywords', [])}")
        print(f"   - Candidates: {hr.get('total_candidates', 0)} (expanded +{hr.get('hypergraph_expanded', 0)})")
        
        if "visualization" in result:
            viz = result["visualization"]
            if "query_path" in viz:
                print(f"   - Visualization: {viz['query_path']}")
            if "ascii_trace" in viz:
                print("\n" + viz["ascii_trace"])
    
    # Generate full graph visualization
    print("\n🖼️  Generating graph visualization...")
    try:
        viz_path = await engine.visualize_graph("demo_graph.html")
        print(f"   Saved to: {viz_path}")
        print(f"   Open in browser to view interactive graph!")
    except Exception as e:
        print(f"   ❌ Visualization failed: {e}")
    
    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


async def run_demo_mode():
    """Run demo without API key using mock data."""
    from hyperhierarchical_rag.Application.memory_manager import MemoryManager
    from hyperhierarchical_rag.Application.query_processor import QueryProcessor
    from hyperhierarchical_rag.visualization import HypergraphVisualizer
    
    print("\n📦 Creating mock data...")
    
    # Create mock nodes
    propofol = HyperNode(
        name="Propofol",
        description="Short-acting anesthetic for sedation",
        level=NodeLevel.LOCAL,
        keywords=["propofol", "sedative", "anesthetic"],
    )
    remimazolam = HyperNode(
        name="Remimazolam",
        description="Novel benzodiazepine with reversal agent",
        level=NodeLevel.LOCAL,
        keywords=["remimazolam", "benzodiazepine", "sedative"],
    )
    delirium = HyperNode(
        name="Delirium",
        description="Acute confusion in ICU patients",
        level=NodeLevel.LOCAL,
        keywords=["delirium", "confusion", "icu"],
    )
    sedation = HyperNode(
        name="Sedation",
        description="Drug-induced reduction of consciousness",
        level=NodeLevel.GLOBAL,
        keywords=["sedation", "anesthesia", "consciousness"],
    )
    icu_care = HyperNode(
        name="ICU Care",
        description="Critical care medicine practices",
        level=NodeLevel.GLOBAL,
        keywords=["icu", "critical", "care"],
    )
    
    nodes = [propofol, remimazolam, delirium, sedation, icu_care]
    
    # Create hyperedges (n-ary relations)
    edge1 = HyperEdge(
        node_ids={propofol.id, remimazolam.id, sedation.id},
        relation="sedation_drugs",
        context="Both propofol and remimazolam are used for sedation",
        weight=0.9,
    )
    edge2 = HyperEdge(
        node_ids={remimazolam.id, delirium.id, icu_care.id},
        relation="delirium_reduction",
        context="Remimazolam may reduce delirium in ICU",
        weight=0.7,
    )
    edge3 = HyperEdge(
        node_ids={propofol.id, delirium.id, sedation.id, icu_care.id},
        relation="sedation_complications",
        context="Deep sedation with propofol can increase delirium risk",
        weight=0.6,
    )
    
    edges = [edge1, edge2, edge3]
    
    print(f"   Created {len(nodes)} nodes and {len(edges)} hyperedges")
    
    # Show the cross-level connection
    print("\n🔗 Hyperedge Connections (showing cross-level):")
    for edge in edges:
        member_names = []
        for node in nodes:
            if node.id in edge.node_ids:
                member_names.append(f"[{node.level.value.upper()}] {node.name}")
        print(f"   {edge.relation}: {' ↔ '.join(member_names)}")
    
    # Generate visualization
    print("\n🖼️  Generating visualization...")
    viz = HypergraphVisualizer()
    html_path = viz.to_html(
        nodes=nodes,
        edges=edges,
        title="HyperHierarchicalRAG Demo Graph",
        filename="demo_mock_graph.html",
    )
    print(f"   Saved to: {html_path}")
    print(f"   Open in browser to view interactive graph!")
    
    # Show the key insight
    print("\n" + "=" * 70)
    print("💡 KEY INSIGHT: Cross-Level Hyperedges")
    print("=" * 70)
    print("""
    In this demo, you can see how hyperedges connect BOTH:
    - LOCAL nodes (specific entities: Propofol, Remimazolam, Delirium)
    - GLOBAL nodes (abstract themes: Sedation, ICU Care)
    
    This is the power of HyperHierarchicalRAG:
    1. LightRAG provides hierarchical keyword extraction (LOCAL vs GLOBAL)
    2. HGMem provides n-ary hyperedges (connecting multiple concepts)
    3. Combined: A single hyperedge can link specific drugs to broader themes!
    
    Example hyperedge:
    {Propofol, Delirium, Sedation, ICU Care}
    
    This means: When querying about "propofol", the system can discover
    "delirium" via this n-ary connection - something binary KG edges can't do!
    """)


if __name__ == "__main__":
    asyncio.run(main())
