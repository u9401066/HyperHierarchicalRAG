"""
IHypergraphRepository - Interface for hypergraph storage operations.

Following DDD pattern: Interface defined in Domain, implementation in Infrastructure.

References:
- DDD Bylaw: .github/bylaws/ddd-architecture.md (Section 3.1)
- HGMem: external/HGMem/myrag/memory.py (storage patterns)
"""

from abc import ABC, abstractmethod
from typing import Any

from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel


class IHypergraphRepository(ABC):
    """
    Abstract interface for hypergraph storage.

    Implementations:
    - InMemoryHypergraphRepository (MVP)
    - Neo4jHypergraphRepository (future)
    - PostgresHypergraphRepository (future)
    """

    # ==================== Node Operations ====================

    @abstractmethod
    async def get_node(self, node_id: str) -> HyperNode | None:
        """Get a node by ID."""
        ...

    @abstractmethod
    async def get_nodes(self, node_ids: list[str]) -> list[HyperNode]:
        """Get multiple nodes by IDs."""
        ...

    @abstractmethod
    async def upsert_node(self, node: HyperNode) -> HyperNode:
        """Insert or update a node."""
        ...

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its associated edges."""
        ...

    @abstractmethod
    async def has_node(self, node_id: str) -> bool:
        """Check if a node exists."""
        ...

    # ==================== Edge Operations ====================

    @abstractmethod
    async def get_edge(self, edge_id: str) -> HyperEdge | None:
        """Get an edge by ID."""
        ...

    @abstractmethod
    async def get_edges_for_node(self, node_id: str) -> list[HyperEdge]:
        """Get all edges connected to a node."""
        ...

    @abstractmethod
    async def upsert_edge(self, edge: HyperEdge) -> HyperEdge:
        """Insert or update an edge."""
        ...

    @abstractmethod
    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        ...

    # ==================== Query Operations ====================

    @abstractmethod
    async def find_by_keywords(
        self,
        keywords: list[str],
        level: NodeLevel | None = None,
    ) -> list[HyperNode]:
        """Find nodes by keywords."""
        ...

    @abstractmethod
    async def find_connected_nodes(
        self,
        node_id: str,
        max_hops: int = 2,
    ) -> list[HyperNode]:
        """Find nodes connected via hyperedges."""
        ...

    @abstractmethod
    async def get_hyperedge(self, node_ids: list[str]) -> HyperEdge | None:
        """Get a hyperedge by its member nodes."""
        ...

    # ==================== Statistics ====================

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get repository statistics."""
        ...

    # ==================== Chunk Operations ====================

    @abstractmethod
    async def upsert_chunk(
        self,
        chunk_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        source_id: str | None = None,
    ) -> None:
        """保存文本切片與元數據"""
        ...

    @abstractmethod
    async def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """獲取指定切片"""
        ...

    # ==================== Memory Points Operations ====================

    @abstractmethod
    async def save_memory_point(
        self, involved_objects: list[str], description: str, source_query: str | None = None
    ) -> int:
        """Save a memory point to persistent storage."""
        ...

    @abstractmethod
    async def load_all_memory_points(self) -> list[dict[str, Any]]:
        """Load all memory points from storage."""
        ...

    @abstractmethod
    async def delete_memory_point(self, memory_id: int) -> bool:
        """Delete a memory point."""
        ...

    @abstractmethod
    async def clear_memory_points(self) -> None:
        """Clear all memory points."""
        ...

    # ==================== Workspace / Session Operations ====================

    @abstractmethod
    async def save_subquery_history(self, session_id: str, subqueries: list[str]) -> None:
        """Save subquery history for a session."""
        ...

    @abstractmethod
    async def load_subquery_history(self, session_id: str) -> list[str]:
        """Load subquery history for a session."""
        ...

    # ==================== System Methods ====================

    @abstractmethod
    async def clear_all(self) -> None:
        """Clear all data from storage."""
        ...
