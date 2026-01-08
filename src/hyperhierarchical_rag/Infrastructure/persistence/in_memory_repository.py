"""
InMemoryHypergraphRepository - In-memory implementation of hypergraph storage.

MVP implementation for development and testing.
Future: Replace with Neo4j, PostgreSQL + pgvector, or dedicated graph database.

References:
- HGMem: external/HGMem/myrag/memory.py (Memory class storage patterns)
- DDD Bylaw: .github/bylaws/ddd-architecture.md (Repository pattern)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel
from hyperhierarchical_rag.Domain.repositories import IHypergraphRepository

logger = logging.getLogger(__name__)


class InMemoryHypergraphRepository(IHypergraphRepository):
    """
    In-memory implementation of IHypergraphRepository.

    Features:
    - Fast CRUD operations for nodes and edges
    - Keyword-based inverted index for retrieval
    - JSON serialization for persistence
    - Thread-safe operations (via async)

    Limitations:
    - All data in memory (not suitable for large graphs)
    - No vector similarity search (use VectorRepository for that)
    """

    def __init__(self, persist_path: Optional[str] = None) -> None:
        """
        Initialize the repository.

        Args:
            persist_path: Optional path to persist data as JSON
        """
        self._nodes: Dict[str, HyperNode] = {}
        self._edges: Dict[str, HyperEdge] = {}
        self._keyword_index: Dict[str, Set[str]] = {}  # keyword -> node_ids
        self._node_to_edges: Dict[str, Set[str]] = {}  # node_id -> edge_ids
        self._persist_path = Path(persist_path) if persist_path else None

        # Load from disk if exists
        if self._persist_path and self._persist_path.exists():
            self._load_from_disk()

        logger.info(f"InMemoryHypergraphRepository initialized (persist={persist_path})")

    # ==================== Node Operations ====================

    async def get_node(self, node_id: str) -> Optional[HyperNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    async def get_nodes(self, node_ids: List[str]) -> List[HyperNode]:
        """Get multiple nodes by IDs."""
        return [self._nodes[nid] for nid in node_ids if nid in self._nodes]

    async def upsert_node(self, node: HyperNode) -> HyperNode:
        """Insert or update a node."""
        # Remove old keywords from index
        if node.id in self._nodes:
            old_node = self._nodes[node.id]
            for kw in old_node.keywords:
                if kw in self._keyword_index:
                    self._keyword_index[kw].discard(node.id)

        # Store node
        self._nodes[node.id] = node

        # Update keyword index
        for kw in node.keywords:
            if kw not in self._keyword_index:
                self._keyword_index[kw] = set()
            self._keyword_index[kw].add(node.id)

        # Initialize edge tracking
        if node.id not in self._node_to_edges:
            self._node_to_edges[node.id] = set()

        await self._persist()
        return node

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its associated edges."""
        if node_id not in self._nodes:
            return False

        node = self._nodes[node_id]

        # Remove from keyword index
        for kw in node.keywords:
            if kw in self._keyword_index:
                self._keyword_index[kw].discard(node_id)

        # Remove associated edges
        if node_id in self._node_to_edges:
            for edge_id in list(self._node_to_edges[node_id]):
                await self.delete_edge(edge_id)
            del self._node_to_edges[node_id]

        # Remove node
        del self._nodes[node_id]

        await self._persist()
        return True

    async def has_node(self, node_id: str) -> bool:
        """Check if a node exists."""
        return node_id in self._nodes

    # ==================== Edge Operations ====================

    async def get_edge(self, edge_id: str) -> Optional[HyperEdge]:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    async def get_edges_for_node(self, node_id: str) -> List[HyperEdge]:
        """Get all edges connected to a node."""
        if node_id not in self._node_to_edges:
            return []
        return [self._edges[eid] for eid in self._node_to_edges[node_id] if eid in self._edges]

    async def upsert_edge(self, edge: HyperEdge) -> HyperEdge:
        """Insert or update an edge."""
        # Remove old node associations
        if edge.id in self._edges:
            old_edge = self._edges[edge.id]
            for node_id in old_edge.node_ids:
                if node_id in self._node_to_edges:
                    self._node_to_edges[node_id].discard(edge.id)

        # Store edge
        self._edges[edge.id] = edge

        # Update node-to-edge mapping
        for node_id in edge.node_ids:
            if node_id not in self._node_to_edges:
                self._node_to_edges[node_id] = set()
            self._node_to_edges[node_id].add(edge.id)

        await self._persist()
        return edge

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        if edge_id not in self._edges:
            return False

        edge = self._edges[edge_id]

        # Remove from node mappings
        for node_id in edge.node_ids:
            if node_id in self._node_to_edges:
                self._node_to_edges[node_id].discard(edge_id)

        # Remove edge
        del self._edges[edge_id]

        await self._persist()
        return True

    # ==================== Query Operations ====================

    async def find_by_keywords(
        self,
        keywords: List[str],
        level: Optional[NodeLevel] = None,
    ) -> List[HyperNode]:
        """
        Find nodes by keywords.

        Args:
            keywords: Keywords to search for
            level: Optional filter by node level

        Returns:
            Matching nodes
        """
        matching_ids: Set[str] = set()

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in self._keyword_index:
                matching_ids.update(self._keyword_index[kw_lower])

        results = []
        for node_id in matching_ids:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                if level is None or node.level == level:
                    results.append(node)

        return results

    async def find_connected_nodes(
        self,
        node_id: str,
        max_hops: int = 2,
    ) -> List[HyperNode]:
        """
        Find nodes connected via hyperedges (BFS traversal).

        This is the core of HGMem's multi-hop reasoning.

        Args:
            node_id: Starting node ID
            max_hops: Maximum traversal depth

        Returns:
            Connected nodes
        """
        visited: Set[str] = {node_id}
        frontier: Set[str] = {node_id}

        for _ in range(max_hops):
            next_frontier: Set[str] = set()

            for current_id in frontier:
                # Get edges connected to this node
                edges = await self.get_edges_for_node(current_id)

                for edge in edges:
                    # Get other nodes in this hyperedge
                    for connected_id in edge.node_ids:
                        if connected_id not in visited:
                            visited.add(connected_id)
                            next_frontier.add(connected_id)

            frontier = next_frontier
            if not frontier:
                break

        # Remove starting node and return results
        visited.discard(node_id)
        return await self.get_nodes(list(visited))

    async def get_hyperedge(self, node_ids: List[str]) -> Optional[HyperEdge]:
        """Get a hyperedge by its member nodes (HGMem pattern)."""
        node_set = frozenset(node_ids)

        for edge in self._edges.values():
            if frozenset(edge.node_ids) == node_set:
                return edge

        return None

    # ==================== Statistics ====================

    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        local_count = sum(1 for n in self._nodes.values() if n.level == NodeLevel.LOCAL)
        global_count = sum(1 for n in self._nodes.values() if n.level == NodeLevel.GLOBAL)
        binary_count = sum(1 for e in self._edges.values() if e.is_binary)
        nary_count = sum(1 for e in self._edges.values() if not e.is_binary)

        return {
            "nodes": {
                "total": len(self._nodes),
                "local": local_count,
                "global": global_count,
            },
            "edges": {
                "total": len(self._edges),
                "binary": binary_count,
                "n_ary": nary_count,
            },
            "keywords_indexed": len(self._keyword_index),
        }

    # ==================== Persistence ====================

    async def _persist(self) -> None:
        """Persist data to disk if path is configured."""
        if self._persist_path is None:
            return

        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
                "edges": {eid: e.to_dict() for eid, e in self._edges.items()},
            }

            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Persisted to {self._persist_path}")
        except Exception as e:
            logger.error(f"Failed to persist: {e}")

    def _load_from_disk(self) -> None:
        """Load data from disk."""
        if not self._persist_path or not self._persist_path.exists():
            return

        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Load nodes
            for node_data in data.get("nodes", {}).values():
                node = HyperNode.from_dict(node_data)
                self._nodes[node.id] = node

                # Rebuild keyword index
                for kw in node.keywords:
                    if kw not in self._keyword_index:
                        self._keyword_index[kw] = set()
                    self._keyword_index[kw].add(node.id)

                self._node_to_edges[node.id] = set()

            # Load edges
            for edge_data in data.get("edges", {}).values():
                edge = HyperEdge.from_dict(edge_data)
                self._edges[edge.id] = edge

                # Rebuild node-to-edge mapping
                for node_id in edge.node_ids:
                    if node_id in self._node_to_edges:
                        self._node_to_edges[node_id].add(edge.id)

            logger.info(f"Loaded {len(self._nodes)} nodes, {len(self._edges)} edges from disk")
        except Exception as e:
            logger.error(f"Failed to load from disk: {e}")
