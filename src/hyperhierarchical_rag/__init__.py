"""
HyperHierarchicalRAG - Combining Hypergraph Memory with Hierarchical Retrieval

A novel RAG system that integrates:
- LightRAG's hierarchical keyword retrieval (Local/Global)
- HGMem's hypergraph working memory (n-ary relations + evolve)

Exposed as MCP tools for AI Agent integration.

Usage:
    from hyperhierarchical_rag import RAGEngine

    engine = RAGEngine.from_env()
    await engine.initialize()

    await engine.insert("Your document text...")
    result = await engine.query("Your question", visualize=True)
"""

__version__ = "0.1.0"
__author__ = "u9401066"

from hyperhierarchical_rag.config import HyperHierarchicalConfig, get_config
from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel
from hyperhierarchical_rag.engine import RAGEngine

__all__ = [
    "RAGEngine",
    "HyperHierarchicalConfig",
    "get_config",
    "HyperNode",
    "HyperEdge",
    "NodeLevel",
]
