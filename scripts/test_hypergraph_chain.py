"""Test Hypergraph Chain Expansion - Core HGMem Feature."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from hyperhierarchical_rag.engine import RAGEngine


async def test_hypergraph_chain():
    engine = RAGEngine.from_env()
    await engine.initialize()

    print("=== Testing Hypergraph Chain Expansion ===")
    print(f"Memory Points: {len(engine._memory_evolver.memory_points)}")

    # First, let's do a query with memory evolution to create some memory points
    print("\n--- Query 1: Creating Memory Points ---")
    result1 = await engine.query(
        query="What is RAG retrieval augmented generation?", mode="hybrid", evolve_memory=True
    )
    lightrag_resp = result1.get("lightrag_response", "")
    print(f"LightRAG response length: {len(str(lightrag_resp))}")
    print(f"Memory Points after Q1: {len(engine._memory_evolver.memory_points)}")

    # Print created memory points
    for i, mp in enumerate(engine._memory_evolver.memory_points):
        print(f"  MP[{i}]: {{{', '.join(mp.involved_objects)}}}")

    # Test hypergraph expansion directly
    print("\n--- Direct Hypergraph Expansion Test ---")
    expanded = await engine._expand_via_hypergraph(
        query="How does knowledge graph help LLM?",
        retrieved_context="Knowledge graphs can enhance large language models by providing structured information.",
        max_hops=2,
    )
    print("Direct expansion result:")
    print(f"  Seed entities: {expanded.get('seed_entities', [])}")
    print(f"  Memory points used: {expanded.get('memory_points_used', 0)}")
    print(f"  Discovered entities: {expanded.get('discovered_entities', [])}")
    print(f"  New entities: {expanded.get('new_entities', 0)}")
    print(f"  Hops: {expanded.get('hops', 0)}")

    # Second query - should discover related entities via hypergraph
    print("\n--- Query 2: Testing Hypergraph Expansion ---")
    result2 = await engine.query(
        query="How does knowledge graph improve LLM response quality?",
        mode="hybrid",
        evolve_memory=True,
    )

    print(f"Result2 keys: {result2.keys()}")

    if "hypergraph_expanded" in result2:
        expanded = result2["hypergraph_expanded"]
        print("\n✅ Hypergraph Expansion Results:")
        print(f"   Seed entities: {expanded.get('seed_entities', [])}")
        print(f"   Memory points used: {expanded.get('memory_points_used', 0)}")
        print(f"   Discovered entities: {expanded.get('discovered_entities', [])}")
        print(f"   New entities: {expanded.get('new_entities', 0)}")
        print(f"   Hops: {expanded.get('hops', 0)}")
        if expanded.get("expanded_context"):
            print("\n   Expanded Context Preview:")
            print("   " + expanded["expanded_context"][:500].replace("\n", "\n   "))
    else:
        print("\n⚠️  No hypergraph expansion (may need more memory points)")

    print(f"\nFinal Memory Points: {len(engine._memory_evolver.memory_points)}")
    for i, mp in enumerate(engine._memory_evolver.memory_points):
        print(f"  MP[{i}]: {{{', '.join(mp.involved_objects)}}}")


if __name__ == "__main__":
    asyncio.run(test_hypergraph_chain())
