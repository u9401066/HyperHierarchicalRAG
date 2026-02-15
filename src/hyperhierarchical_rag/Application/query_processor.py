"""
QueryProcessor - Unified query interface combining hierarchical and hypergraph retrieval.

Integrates:
- LightRAG's hierarchical routing (Local/Global keywords)
- HGMem's hypergraph reasoning and memory evolution

KEY INTEGRATION POINT:
1. LightRAG provides: Hierarchical keyword extraction + KG retrieval
2. HGMem provides: Hyperedge traversal + Memory evolution
3. Combined: Hierarchical keywords → KG candidates → Hypergraph expansion → Evolved memory

References:
- external/LightRAG/lightrag/lightrag.py
- external/HGMem/myrag/memory.py
"""

import logging
from collections.abc import Callable
from typing import Any

from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel
from hyperhierarchical_rag.Domain.repositories import IHypergraphRepository
from hyperhierarchical_rag.Domain.services.memory_evolver import MemoryEvolver, MemoryPoint

logger = logging.getLogger(__name__)


class QueryProcessor:
    """
    Unified query processor combining hierarchical and hypergraph retrieval.

    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                     Query Flow (LightRAG + HGMem)                      ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                        ║
    ║  User Query                                                            ║
    ║      │                                                                 ║
    ║      ▼                                                                 ║
    ║  ┌─────────────────────────────────────────────────────────────────┐  ║
    ║  │ Step 1: LightRAG Hierarchical Keyword Extraction                │  ║
    ║  │         → ll_keywords (Local): entity-level                     │  ║
    ║  │         → hl_keywords (Global): theme-level                     │  ║
    ║  └─────────────────────────────────────────────────────────────────┘  ║
    ║      │                                                                 ║
    ║      ▼                                                                 ║
    ║  ┌─────────────────────────────────────────────────────────────────┐  ║
    ║  │ Step 2: Retrieve Candidates from Knowledge Graph                │  ║
    ║  │         → Local nodes (entities matching ll_keywords)           │  ║
    ║  │         → Global nodes (themes matching hl_keywords)            │  ║
    ║  └─────────────────────────────────────────────────────────────────┘  ║
    ║      │                                                                 ║
    ║      ▼                                                                 ║
    ║  ┌─────────────────────────────────────────────────────────────────┐  ║
    ║  │ Step 3: HGMem Hyperedge Traversal (KEY DIFFERENCE!)             │  ║
    ║  │         → Traverse n-ary hyperedges from candidate nodes        │  ║
    ║  │         → Discover connected entities via multi-hop BFS         │  ║
    ║  │         → This finds relationships LightRAG alone cannot!       │  ║
    ║  └─────────────────────────────────────────────────────────────────┘  ║
    ║      │                                                                 ║
    ║      ▼                                                                 ║
    ║  ┌─────────────────────────────────────────────────────────────────┐  ║
    ║  │ Step 4: Memory Evolution (HGMem)                                │  ║
    ║  │         → LLM analyzes retrieved context                        │  ║
    ║  │         → Extracts new memory points (n-ary relations)          │  ║
    ║  │         → Updates hypergraph for future queries                 │  ║
    ║  └─────────────────────────────────────────────────────────────────┘  ║
    ║      │                                                                 ║
    ║      ▼                                                                 ║
    ║  ┌─────────────────────────────────────────────────────────────────┐  ║
    ║  │ Step 5: Generate Response                                       │  ║
    ║  │         → Rank and aggregate results                            │  ║
    ║  │         → Return enriched context                               │  ║
    ║  └─────────────────────────────────────────────────────────────────┘  ║
    ║                                                                        ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """

    def __init__(
        self,
        repository: IHypergraphRepository | None = None,
        llm_func: Callable | None = None,
    ) -> None:
        """
        Initialize QueryProcessor.

        Args:
            repository: Hypergraph repository for storage
            llm_func: LLM function for keyword extraction and memory evolution
        """
        self._repository = repository
        self._llm_func = llm_func
        self._memory_evolver = MemoryEvolver(llm_func=llm_func)
        self._memory_points: list[MemoryPoint] = []

        # Fallback in-memory storage if no repository provided
        self._nodes: dict[str, HyperNode] = {}
        self._edges: dict[str, HyperEdge] = {}

        logger.info("QueryProcessor initialized")

    def set_llm_func(self, llm_func: Callable) -> None:
        """Set LLM function for all components."""
        self._llm_func = llm_func
        self._memory_evolver.set_llm_func(llm_func)

    async def query_hybrid(
        self,
        query: str,
        top_k: int = 10,
        use_hypergraph: bool = True,
        evolve_memory: bool = True,
    ) -> dict[str, Any]:
        """
        Execute hybrid query combining hierarchical retrieval and hypergraph reasoning.

        This is the MAIN ENTRY POINT that combines LightRAG + HGMem.

        Args:
            query: Query text
            top_k: Number of results to return
            use_hypergraph: Whether to enable hypergraph expansion
            evolve_memory: Whether to evolve memory after query

        Returns:
            Query results with entities, relations, context, and hypergraph expansions
        """
        logger.info(f"Hybrid query: {query[:50]}...")

        # ===== Step 1: LightRAG Hierarchical Keyword Extraction =====
        local_keywords = await self._extract_local_keywords(query)
        global_keywords = await self._extract_global_keywords(query)

        logger.debug(f"Keywords - Local: {local_keywords}, Global: {global_keywords}")

        # ===== Step 2: Retrieve Candidates from Knowledge Graph =====
        local_nodes = await self._retrieve_by_keywords(local_keywords, NodeLevel.LOCAL)
        global_nodes = await self._retrieve_by_keywords(global_keywords, NodeLevel.GLOBAL)

        lightrag_candidates = list(set(local_nodes + global_nodes))
        logger.debug(f"LightRAG candidates: {len(lightrag_candidates)} nodes")

        # ===== Step 3: HGMem Hyperedge Traversal (KEY INTEGRATION!) =====
        hypergraph_expanded = []
        if use_hypergraph and lightrag_candidates:
            hypergraph_expanded = await self._expand_via_hyperedges(lightrag_candidates, max_hops=2)
            logger.debug(f"Hypergraph expanded: {len(hypergraph_expanded)} additional nodes")

        # Combine all candidates
        all_candidates = list(set(lightrag_candidates + hypergraph_expanded))

        # ===== Step 4: Memory Evolution (HGMem) =====
        if evolve_memory and all_candidates:
            # Build context from candidates
            retrieved_context = self._build_context_from_nodes(all_candidates)

            # Evolve memory (LLM analyzes and extracts new memory points)
            evolve_result = await self._memory_evolver.evolve(
                retrieved_info=retrieved_context,
                main_query=query,
                subqueries=[],  # Could be expanded for multi-step reasoning
                existing_memory_points=self._memory_points,
            )

            # Convert new memory points to hyperedges and store
            await self._store_evolved_memory(evolve_result)

            logger.debug(f"Memory evolved: {len(evolve_result.inserted_points)} new points")

        # ===== Step 5: Rank and Return Results =====
        results = await self._rank_results(query, all_candidates[:top_k])

        return {
            "query": query,
            "mode": "hybrid",
            "local_keywords": local_keywords,
            "global_keywords": global_keywords,
            "lightrag_candidates": len(lightrag_candidates),
            "hypergraph_expanded": len(hypergraph_expanded),
            "total_candidates": len(all_candidates),
            "results": results,
            "memory_points": len(self._memory_points),
        }

    async def query_local(
        self,
        query: str,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """
        Execute local (entity-level) keyword query.
        Corresponds to ll_keywords in LightRAG.
        """
        logger.info(f"Local query: {query[:50]}...")

        keywords = await self._extract_local_keywords(query)
        nodes = await self._retrieve_by_keywords(keywords, NodeLevel.LOCAL)
        results = await self._rank_results(query, nodes[:top_k])

        return {
            "query": query,
            "mode": "local",
            "keywords": keywords,
            "results": results,
            "total": len(results),
        }

    async def query_global(
        self,
        query: str,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """
        Execute global (theme-level) semantic query.
        Corresponds to hl_keywords in LightRAG.
        """
        logger.info(f"Global query: {query[:50]}...")

        keywords = await self._extract_global_keywords(query)
        nodes = await self._retrieve_by_keywords(keywords, NodeLevel.GLOBAL)
        results = await self._rank_results(query, nodes[:top_k])

        return {
            "query": query,
            "mode": "global",
            "keywords": keywords,
            "results": results,
            "total": len(results),
        }

    # ==================== LightRAG Integration ====================

    async def _extract_local_keywords(self, query: str) -> list[str]:
        """
        Extract local (entity) keywords from query.

        Uses LightRAG's keyword extraction or LLM-based extraction.
        These are ll_keywords in LightRAG - specific entities, names, terms.
        """
        if self._llm_func:
            # TODO: Use LLM for better extraction
            pass

        # Simple extraction fallback
        import re

        words = query.lower().split()
        # Extract longer words (likely entities)
        keywords = [w for w in words if len(w) > 3 and w.isalpha()]
        # Also extract capitalized words (proper nouns)
        proper_nouns = re.findall(r"\b[A-Z][a-z]+\b", query)
        keywords.extend([n.lower() for n in proper_nouns])

        return list(set(keywords))[:10]

    async def _extract_global_keywords(self, query: str) -> list[str]:
        """
        Extract global (theme) keywords from query.

        Uses LightRAG's global keyword extraction.
        These are hl_keywords in LightRAG - abstract concepts, themes.
        """
        if self._llm_func:
            # TODO: Use LLM for better extraction
            pass

        # Theme indicator words
        theme_words = [
            "compare",
            "contrast",
            "overview",
            "summary",
            "trend",
            "analysis",
            "relationship",
            "impact",
            "effect",
            "cause",
            "mechanism",
            "process",
            "system",
            "approach",
            "method",
        ]

        words = query.lower().split()
        themes = [w for w in words if w in theme_words]

        return themes if themes else ["general"]

    async def _retrieve_by_keywords(
        self,
        keywords: list[str],
        level: NodeLevel,
    ) -> list[HyperNode]:
        """
        Retrieve nodes by keywords and hierarchical level.

        Uses inverted index for efficient retrieval.
        """
        if self._repository:
            return await self._repository.find_by_keywords(keywords, level)

        # Fallback to in-memory search
        results = []
        for node in self._nodes.values():
            if node.level != level:
                continue
            node_keywords = {k.lower() for k in node.keywords}
            query_keywords = {k.lower() for k in keywords}
            if node_keywords & query_keywords:
                results.append(node)
        return results

    # ==================== HGMem Integration ====================

    async def _expand_via_hyperedges(
        self,
        seed_nodes: list[HyperNode],
        max_hops: int = 2,
    ) -> list[HyperNode]:
        """
        Expand candidates via hyperedge traversal.

        ╔═══════════════════════════════════════════════════════════════════╗
        ║ This is the KEY DIFFERENCE from LightRAG!                         ║
        ║                                                                   ║
        ║ LightRAG: Binary edges only → (A)──[rel]──>(B)                   ║
        ║ HGMem:    N-ary hyperedges  → {A, B, C, D} all connected         ║
        ║                                                                   ║
        ║ Example:                                                          ║
        ║ - Query: "propofol"                                               ║
        ║ - LightRAG finds: Propofol → used_for → Sedation                 ║
        ║ - Hyperedge: {Propofol, Remimazolam, Delirium, ICU}              ║
        ║ - HGMem discovers: Delirium (not directly connected in KG!)      ║
        ╚═══════════════════════════════════════════════════════════════════╝
        """
        if self._repository:
            # Use repository's optimized traversal
            expanded = []
            for node in seed_nodes:
                connected = await self._repository.find_connected_nodes(node.id, max_hops=max_hops)
                expanded.extend(connected)
            return list(set(expanded))

        # Fallback to in-memory BFS traversal
        expanded = []
        visited = {n.id for n in seed_nodes}
        current_frontier = seed_nodes.copy()

        for _hop in range(max_hops):
            next_frontier = []

            for node in current_frontier:
                # Find all hyperedges containing this node
                for edge in self._edges.values():
                    if node.id not in edge.node_ids:
                        continue

                    # Get all OTHER nodes connected via this hyperedge
                    for other_id in edge.node_ids:
                        if other_id not in visited and other_id in self._nodes:
                            other_node = self._nodes[other_id]
                            expanded.append(other_node)
                            visited.add(other_id)
                            next_frontier.append(other_node)

            current_frontier = next_frontier
            if not current_frontier:
                break

        return expanded

    async def _store_evolved_memory(self, evolve_result: Any) -> None:
        """Store evolved memory points as hyperedges."""
        # Build node ID map
        node_id_map = {n.name.upper(): n.id for n in self._nodes.values()}

        # Store inserted points
        for point in evolve_result.inserted_points:
            self._memory_points.append(point)

            # Ensure nodes exist for all involved objects
            for obj in point.involved_objects:
                if obj not in node_id_map:
                    node = HyperNode(
                        name=obj,
                        level=NodeLevel.LOCAL,
                        keywords=[obj.lower()],
                    )
                    self._nodes[node.id] = node
                    node_id_map[obj] = node.id

                    if self._repository:
                        await self._repository.upsert_node(node)

            # Create hyperedge
            edge = self._memory_evolver.memory_point_to_hyperedge(point, node_id_map)
            self._edges[edge.id] = edge

            if self._repository:
                await self._repository.upsert_edge(edge)

        # Handle updated points
        for idx, point in evolve_result.updated_points:
            if idx < len(self._memory_points):
                self._memory_points[idx] = point

    def _build_context_from_nodes(self, nodes: list[HyperNode]) -> str:
        """Build text context from nodes for memory evolution."""
        lines = []
        for node in nodes:
            lines.append(f"Entity: {node.name}")
            if node.description:
                lines.append(f"Description: {node.description}")
            lines.append(f"Level: {node.level.value}")
            lines.append("")
        return "\n".join(lines)

    async def _rank_results(
        self,
        query: str,
        nodes: list[HyperNode],
    ) -> list[dict[str, Any]]:
        """Rank nodes by relevance to query."""
        # TODO: Use embedding similarity for ranking
        return [node.to_dict() for node in nodes]

    # ==================== Node/Edge Management ====================

    def add_node(self, node: HyperNode) -> None:
        """Add a node to the processor."""
        self._nodes[node.id] = node

    def add_edge(self, edge: HyperEdge) -> None:
        """Add an edge to the processor."""
        self._edges[edge.id] = edge
