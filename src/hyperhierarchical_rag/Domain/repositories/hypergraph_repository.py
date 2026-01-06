"""
IHypergraphRepository - Interface for hypergraph storage operations.

Following DDD pattern: Interface defined in Domain, implementation in Infrastructure.

References:
- DDD Bylaw: .github/bylaws/ddd-architecture.md (Section 3.1)
- HGMem: external/HGMem/myrag/memory.py (storage patterns)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from hyperhierarchical_rag.Domain.entities import HyperNode, HyperEdge, NodeLevel


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
    async def get_node(self, node_id: str) -> Optional[HyperNode]:
        """Get a node by ID."""
        ...
    
    @abstractmethod
    async def get_nodes(self, node_ids: List[str]) -> List[HyperNode]:
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
    async def get_edge(self, edge_id: str) -> Optional[HyperEdge]:
        """Get an edge by ID."""
        ...
    
    @abstractmethod
    async def get_edges_for_node(self, node_id: str) -> List[HyperEdge]:
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
        keywords: List[str],
        level: Optional[NodeLevel] = None,
    ) -> List[HyperNode]:
        """Find nodes by keywords."""
        ...
    
    @abstractmethod
    async def find_connected_nodes(
        self,
        node_id: str,
        max_hops: int = 2,
    ) -> List[HyperNode]:
        """Find nodes connected via hyperedges."""
        ...
    
    @abstractmethod
    async def get_hyperedge(self, node_ids: List[str]) -> Optional[HyperEdge]:
        """Get a hyperedge by its member nodes."""
        ...
    
    # ==================== Statistics ====================
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        ...

