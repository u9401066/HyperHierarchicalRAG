"""
HyperNode - Entity node in the hypergraph

Combines LightRAG's hierarchical concept with HGMem's node structure.

References:
- LightRAG: Local/Global keyword levels
- HGMem: Node with embedding and description
- Data Model: docs/architecture/data-model.md
"""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class NodeLevel(Enum):
    """
    Hierarchical level of the node (from LightRAG).

    - LOCAL: Specific entities (ll_keywords in LightRAG)
    - GLOBAL: Abstract concepts/themes (hl_keywords in LightRAG)
    """

    LOCAL = "local"
    GLOBAL = "global"


@dataclass
class HyperNode:
    """
    Entity node in the hypergraph.

    Attributes:
        id: Unique identifier (hash of name by default)
        name: Entity name
        description: Entity description with context
        level: Hierarchical level (LOCAL or GLOBAL)
        keywords: Keywords for inverted index (from LightRAG)
        embedding: Semantic embedding vector (optional, computed lazily)
        source_id: Source document ID
    """

    name: str
    description: str = ""
    level: NodeLevel = NodeLevel.LOCAL
    keywords: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    source_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        """Generate ID from name hash if not provided."""
        if self.id == str(uuid4()):  # Default was used
            self.id = self._generate_id(self.name)

    @staticmethod
    def _generate_id(name: str) -> str:
        """Generate a deterministic ID from the entity name."""
        return hashlib.sha256(name.encode()).hexdigest()[:16]

    def add_keyword(self, keyword: str) -> None:
        """Add a keyword for indexing."""
        if keyword not in self.keywords:
            self.keywords.append(keyword)

    def set_embedding(self, embedding: list[float]) -> None:
        """Set the semantic embedding vector."""
        self.embedding = embedding

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "level": self.level.value,
            "keywords": self.keywords,
            "embedding": self.embedding,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HyperNode":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data["name"],
            description=data.get("description", ""),
            level=NodeLevel(data.get("level", "local")),
            keywords=data.get("keywords", []),
            embedding=data.get("embedding"),
            source_id=data.get("source_id"),
        )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HyperNode):
            return False
        return self.id == other.id
