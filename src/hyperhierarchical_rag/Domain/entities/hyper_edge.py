"""
HyperEdge - N-ary relation in the hypergraph

Core innovation from HGMem: supports relations connecting multiple nodes,
going beyond traditional binary (subject-predicate-object) relations.

References:
- HGMem: Hyperedge for n-ary relations, Memory.evolve()
- Data Model: docs/architecture/data-model.md
"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class HyperEdge:
    """
    Hyperedge connecting multiple nodes (n-ary relation).

    Key difference from traditional Knowledge Graph edges:
    - Traditional KG: (Subject) -[Predicate]-> (Object) [binary]
    - HyperEdge: {Node1, Node2, Node3, ...} [n-ary]

    Attributes:
        id: Unique identifier
        node_ids: Set of connected node IDs (n-ary)
        relation: Relation type description
        weight: Relation strength/importance (0.0 - 1.0)
        context: Text context where this relation appears
        evolve_count: Number of times this edge has evolved (from HGMem)
        source_id: Source document ID
    """

    node_ids: set[str]
    relation: str = ""
    weight: float = 1.0
    context: str = ""
    evolve_count: int = 0
    source_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        """Ensure node_ids is a set."""
        if not isinstance(self.node_ids, set):
            self.node_ids = set(self.node_ids)

    @property
    def arity(self) -> int:
        """Return the number of nodes connected by this edge."""
        return len(self.node_ids)

    @property
    def is_binary(self) -> bool:
        """Check if this is a traditional binary relation."""
        return self.arity == 2

    def add_node(self, node_id: str) -> None:
        """Add a node to this hyperedge."""
        self.node_ids.add(node_id)

    def remove_node(self, node_id: str) -> None:
        """Remove a node from this hyperedge."""
        self.node_ids.discard(node_id)

    def evolve(self, new_context: str = "", weight_delta: float = 0.1) -> None:
        """
        Evolve this edge (from HGMem Memory.evolve() concept).

        Called when:
        - New evidence strengthens this relation
        - Query retrieval reinforces this connection

        Args:
            new_context: Additional context to append
            weight_delta: Amount to increase weight (capped at 1.0)
        """
        self.evolve_count += 1
        self.weight = min(1.0, self.weight + weight_delta)
        if new_context:
            self.context = f"{self.context}\n---\n{new_context}".strip()

    def decay(self, decay_rate: float = 0.05) -> None:
        """
        Decay this edge's weight over time (memory forgetting).

        Args:
            decay_rate: Amount to decrease weight (floored at 0.0)
        """
        self.weight = max(0.0, self.weight - decay_rate)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "node_ids": list(self.node_ids),
            "relation": self.relation,
            "weight": self.weight,
            "context": self.context,
            "evolve_count": self.evolve_count,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HyperEdge":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            node_ids=set(data.get("node_ids", [])),
            relation=data.get("relation", ""),
            weight=data.get("weight", 1.0),
            context=data.get("context", ""),
            evolve_count=data.get("evolve_count", 0),
            source_id=data.get("source_id"),
        )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HyperEdge):
            return False
        return self.id == other.id

    def __repr__(self) -> str:
        return f"HyperEdge({self.relation}, nodes={len(self.node_ids)}, weight={self.weight:.2f})"
