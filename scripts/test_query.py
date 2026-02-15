#!/usr/bin/env python3
"""Test RAG query functionality."""

import asyncio

from hyperhierarchical_rag import RAGEngine


async def test_query() -> None:
    """Test RAG query with inserted papers."""
    engine = RAGEngine.from_env()
    await engine.initialize()

    print("=" * 60)
    print("Testing RAG Query")
    print("=" * 60)

    # Test query
    result = await engine.query(
        "What are the main approaches to RAG described in the papers?",
        mode="hybrid",
        evolve_memory=False,  # Skip memory evolution for speed
    )

    # Result uses 'lightrag_response' key
    response = result.get("lightrag_response", "No response")
    print(f"\nResponse:\n{response}")
    print(f"\nMode: {result.get('mode')}")

    # Also test simple query
    print("\n" + "=" * 60)
    print("Testing Simple Query")
    print("=" * 60)

    simple_response = await engine.query_simple("Compare AR-RAG and EVOR approaches", mode="local")
    print(f"\nSimple Response:\n{simple_response}")


if __name__ == "__main__":
    asyncio.run(test_query())
