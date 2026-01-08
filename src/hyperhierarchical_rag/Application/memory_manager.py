"""
MemoryManager - Document and hypergraph memory management.

Handles:
- Document CRUD operations
- Entity and relation extraction
- Memory evolution (from HGMem)

References:
- external/HGMem/myrag/memory.py (Memory.evolve())
- external/LightRAG/lightrag/lightrag.py (insert/query)
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Manages documents and hypergraph memory.

    Responsibilities:
    1. Document ingestion and storage
    2. Entity/relation extraction (via LightRAG patterns)
    3. Hypergraph construction and evolution (via HGMem patterns)
    """

    def __init__(self) -> None:
        """Initialize MemoryManager."""
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._nodes: Dict[str, HyperNode] = {}
        self._edges: Dict[str, HyperEdge] = {}
        logger.info("MemoryManager initialized")

    # ==================== Document CRUD ====================

    async def insert_document(
        self,
        text: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Insert a document and extract knowledge graph.

        Flow:
        1. Store document
        2. Extract entities (nodes)
        3. Extract relations (hyperedges)
        4. Update hypergraph

        TODO: Integrate LightRAG's entity extraction
        Reference: external/LightRAG/lightrag/kg/
        """
        doc_id = doc_id or str(uuid4())

        # Store document
        self._documents[doc_id] = {
            "id": doc_id,
            "text": text,
            "metadata": metadata or {},
            "status": "processing",
        }

        logger.info(f"Inserting document: {doc_id}")

        # TODO: Extract entities using LightRAG
        # For now, create placeholder entities
        entities = await self._extract_entities(text, doc_id)
        for entity in entities:
            self._nodes[entity.id] = entity

        # TODO: Extract relations using LightRAG
        relations = await self._extract_relations(text, entities, doc_id)
        for relation in relations:
            self._edges[relation.id] = relation

        self._documents[doc_id]["status"] = "completed"
        self._documents[doc_id]["entities"] = len(entities)
        self._documents[doc_id]["relations"] = len(relations)

        return {
            "doc_id": doc_id,
            "status": "completed",
            "entities_extracted": len(entities),
            "relations_extracted": len(relations),
        }

    async def get_documents(self) -> Dict[str, Any]:
        """Get all documents."""
        return {
            "documents": list(self._documents.values()),
            "total": len(self._documents),
        }

    async def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """Delete a document and its associated entities/relations."""
        if doc_id not in self._documents:
            return {"status": "not_found", "doc_id": doc_id}

        # Remove associated nodes
        nodes_to_remove = [nid for nid, node in self._nodes.items() if node.source_id == doc_id]
        for nid in nodes_to_remove:
            del self._nodes[nid]

        # Remove associated edges
        edges_to_remove = [eid for eid, edge in self._edges.items() if edge.source_id == doc_id]
        for eid in edges_to_remove:
            del self._edges[eid]

        # Remove document
        del self._documents[doc_id]

        return {
            "status": "deleted",
            "doc_id": doc_id,
            "nodes_removed": len(nodes_to_remove),
            "edges_removed": len(edges_to_remove),
        }

    # ==================== Entity/Relation Management ====================

    async def create_entities(
        self,
        entities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create multiple entities in the hypergraph."""
        created = []
        for entity_data in entities:
            node = HyperNode(
                name=entity_data["name"],
                description=entity_data.get("description", ""),
                level=NodeLevel(entity_data.get("level", "local")),
                keywords=entity_data.get("keywords", []),
                source_id=entity_data.get("source_id"),
            )
            self._nodes[node.id] = node
            created.append(node.to_dict())

        return {
            "status": "created",
            "entities": created,
            "total": len(created),
        }

    async def create_relations(
        self,
        relations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create hyperedges (n-ary relations) in the graph."""
        created = []
        for relation_data in relations:
            edge = HyperEdge(
                node_ids=set(relation_data["node_ids"]),
                relation=relation_data.get("relation", ""),
                context=relation_data.get("context", ""),
                weight=relation_data.get("weight", 1.0),
                source_id=relation_data.get("source_id"),
            )
            self._edges[edge.id] = edge
            created.append(edge.to_dict())

        return {
            "status": "created",
            "relations": created,
            "total": len(created),
        }

    # ==================== Memory Evolution (HGMem) ====================

    async def evolve(
        self,
        query: Optional[str] = None,
        decay_unused: bool = True,
    ) -> Dict[str, Any]:
        """
        Evolve the hypergraph memory.

        Core HGMem concept: Memory.evolve()
        - Strengthen frequently used edges
        - Decay unused edges
        - Adapt graph structure based on queries

        Reference: external/HGMem/myrag/memory.py
        """
        logger.info(f"Evolving memory (query={query is not None}, decay={decay_unused})")

        evolved_edges = 0
        decayed_edges = 0

        # If query provided, strengthen related edges
        if query:
            # TODO: Find edges related to query and evolve them
            for edge in self._edges.values():
                if query.lower() in edge.context.lower():
                    edge.evolve(new_context=f"Query reinforced: {query}")
                    evolved_edges += 1

        # Decay unused edges
        if decay_unused:
            for edge in self._edges.values():
                if edge.evolve_count == 0:
                    edge.decay()
                    decayed_edges += 1

        return {
            "status": "evolved",
            "edges_evolved": evolved_edges,
            "edges_decayed": decayed_edges,
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
        }

    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        local_nodes = sum(1 for n in self._nodes.values() if n.level == NodeLevel.LOCAL)
        global_nodes = sum(1 for n in self._nodes.values() if n.level == NodeLevel.GLOBAL)
        binary_edges = sum(1 for e in self._edges.values() if e.is_binary)
        nary_edges = sum(1 for e in self._edges.values() if not e.is_binary)

        return {
            "nodes": {
                "total": len(self._nodes),
                "local": local_nodes,
                "global": global_nodes,
            },
            "edges": {
                "total": len(self._edges),
                "binary": binary_edges,
                "n_ary": nary_edges,
            },
            "documents": len(self._documents),
        }

    # ==================== Private Extraction Methods ====================

    async def _extract_entities(
        self,
        text: str,
        doc_id: str,
    ) -> List[HyperNode]:
        """
        Extract entities from text.

        TODO: Integrate LightRAG's entity extraction
        Reference: external/LightRAG/lightrag/kg/graph_extractor.py
        """
        # Placeholder: create simple entities from text
        words = text.split()[:5]  # First 5 words as entities
        entities = []
        for word in words:
            if len(word) > 3:
                node = HyperNode(
                    name=word,
                    description=f"Entity extracted from document {doc_id}",
                    level=NodeLevel.LOCAL,
                    keywords=[word.lower()],
                    source_id=doc_id,
                )
                entities.append(node)
        return entities

    async def _extract_relations(
        self,
        text: str,
        entities: List[HyperNode],
        doc_id: str,
    ) -> List[HyperEdge]:
        """
        Extract relations from text.

        TODO: Integrate LightRAG's relation extraction
        Reference: external/LightRAG/lightrag/kg/graph_extractor.py
        """
        # Placeholder: create a hyperedge connecting all entities
        if len(entities) < 2:
            return []

        edge = HyperEdge(
            node_ids={e.id for e in entities},
            relation="co_occurrence",
            context=text[:200],  # First 200 chars as context
            weight=1.0,
            source_id=doc_id,
        )
        return [edge]
