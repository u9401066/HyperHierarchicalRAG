"""
Configuration for HyperHierarchicalRAG

Centralized configuration for LLM, KG, and system settings.
Uses environment variables with sensible defaults.

INTEGRATION: Uses LightRAG's built-in Ollama support when provider="ollama"
- LLM: lightrag.llm.ollama.ollama_model_complete
- Embedding: lightrag.llm.ollama.ollama_embed

MCP MODE: Supports multi-user with automatic storage backend detection
- PostgreSQL for production multi-user
- SQLite WAL for lightweight multi-user
- JSON/NanoVectorDB for single-user development
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, cast

from dotenv import load_dotenv

# Load .env file
load_dotenv()


class StorageMode(str, Enum):
    """Storage backend mode for different deployment scenarios."""

    LOCAL = "local"  # JSON + NanoVectorDB + NetworkX (single user)
    SQLITE = "sqlite"  # SQLite WAL mode (lightweight multi-user)
    POSTGRES = "postgres"  # PostgreSQL (production multi-user)
    MONGODB = "mongodb"  # MongoDB (document-oriented)
    HYBRID = "hybrid"  # Redis + Milvus + Neo4j (high performance)


# ==================== LightRAG Ollama Integration ====================


def get_ollama_llm_func(host: str, model: str) -> Callable:
    """
    Get LightRAG's Ollama LLM function.

    Uses LightRAG's built-in ollama_model_complete() - no need to reinvent!

    Args:
        host: Ollama server URL (e.g., "http://localhost:11434")
        model: Model name (e.g., "llama3.1", "qwen2.5")

    Returns:
        Async callable for LLM completion
    """
    try:
        from lightrag.llm.ollama import ollama_model_complete  # type: ignore

        # Create a configured function
        async def llm_func(prompt: str, system_prompt: str = "") -> str:
            result = await ollama_model_complete(
                prompt=prompt,
                system_prompt=system_prompt,
                host=host,
                model=model,
            )
            # Handle potential streaming response
            if isinstance(result, str):
                return result
            # If it's an iterator, collect it
            return str(result)

        return llm_func
    except ImportError as err:
        raise ImportError(
            "LightRAG not installed. Run: uv pip install -e ./external/LightRAG"
        ) from err


def get_ollama_embed_func(host: str, model: str = "bge-m3:latest") -> Callable:
    """
    Get LightRAG's Ollama embedding function.

    Uses LightRAG's built-in ollama_embed() - no need for sentence-transformers!

    Args:
        host: Ollama server URL
        model: Embedding model (default: bge-m3:latest)

    Returns:
        Async callable for embedding
    """
    try:
        from lightrag.llm.ollama import ollama_embed  # type: ignore

        async def embed_func(texts: list[str]) -> list[list[float]]:
            result = await ollama_embed(
                texts=texts,
                host=host,
                embed_model=model,
            )
            # Convert numpy array to list if needed
            if hasattr(result, "tolist"):
                return result.tolist()  # type: ignore
            return list(result)

        return embed_func
    except ImportError as err:
        raise ImportError(
            "LightRAG not installed. Run: uv pip install -e ./external/LightRAG"
        ) from err


@dataclass
class LLMConfig:
    """LLM configuration."""

    provider: Literal["openai", "ollama", "azure"] = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    api_base: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_BASE"))
    temperature: float = 0.0
    max_tokens: int = 4096

    # Ollama settings
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )

    # Embedding settings (for Ollama provider)
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    )
    embedding_dim: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "768")))

    def validate(self) -> bool:
        """Check if configuration is valid."""
        return not (self.provider == "openai" and not self.api_key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_base": self.api_base,
            "temperature": self.temperature,
            "has_api_key": bool(self.api_key),
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
        }


@dataclass
class EmbeddingConfig:
    """Embedding model configuration."""

    provider: Literal["openai", "sentence-transformers", "ollama"] = "openai"
    model: str = "text-embedding-3-small"
    dimension: int = 1536

    # Sentence Transformers settings
    st_model: str = "all-MiniLM-L6-v2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "dimension": self.dimension,
        }


@dataclass
class StorageConfig:
    """Storage configuration with auto-detection for multi-user mode."""

    # Storage mode (auto-detected or manual)
    mode: StorageMode = field(default=StorageMode.LOCAL)

    # LightRAG storage backend names
    kv_storage: str = "JsonKVStorage"
    vector_storage: str = "NanoVectorDBStorage"
    graph_storage: str = "NetworkXStorage"
    doc_status_storage: str = "JsonDocStatusStorage"

    # LightRAG storage directories
    lightrag_dir: Path = field(default_factory=lambda: Path("./data/lightrag"))

    # Hypergraph storage
    hypergraph_dir: Path = field(default_factory=lambda: Path("./data/hypergraph"))
    hypergraph_db: str = "hypergraph.db"  # SQLite file name

    # PostgreSQL settings
    postgres_host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    postgres_user: str | None = field(default_factory=lambda: os.getenv("POSTGRES_USER"))
    postgres_password: str | None = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD"))
    postgres_database: str | None = field(default_factory=lambda: os.getenv("POSTGRES_DATABASE"))
    postgres_max_connections: int = 20

    # MongoDB settings
    mongo_uri: str | None = field(default_factory=lambda: os.getenv("MONGO_URI"))
    mongo_database: str | None = field(default_factory=lambda: os.getenv("MONGO_DATABASE"))

    # Redis settings
    redis_uri: str | None = field(default_factory=lambda: os.getenv("REDIS_URI"))

    # Neo4j settings
    neo4j_uri: str | None = field(default_factory=lambda: os.getenv("NEO4J_URI"))
    neo4j_user: str | None = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str | None = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD"))

    # Milvus settings
    milvus_uri: str | None = field(default_factory=lambda: os.getenv("MILVUS_URI"))

    # Visualization output
    viz_dir: Path = field(default_factory=lambda: Path("./data/visualizations"))

    @classmethod
    def auto_detect(cls) -> "StorageConfig":
        """
        Auto-detect storage mode based on available environment variables.

        Priority:
        1. PostgreSQL (if all credentials present)
        2. MongoDB (if MONGO_URI present)
        3. Hybrid (if Redis + other backends)
        4. SQLite (if STORAGE_MODE=sqlite)
        5. Local (default)
        """
        config = cls()

        # Check explicit mode override
        explicit_mode = os.getenv("STORAGE_MODE", "").lower()
        if explicit_mode == "sqlite":
            config.mode = StorageMode.SQLITE
            return config

        # Check PostgreSQL (production multi-user)
        if all([config.postgres_user, config.postgres_password, config.postgres_database]):
            config.mode = StorageMode.POSTGRES
            config.kv_storage = "PGKVStorage"
            config.vector_storage = "PGVectorStorage"
            config.graph_storage = "PGGraphStorage"
            config.doc_status_storage = "PGDocStatusStorage"
            return config

        # Check MongoDB
        if config.mongo_uri and config.mongo_database:
            config.mode = StorageMode.MONGODB
            config.kv_storage = "MongoKVStorage"
            config.vector_storage = "MongoVectorDBStorage"
            config.graph_storage = "MongoGraphStorage"
            config.doc_status_storage = "MongoDocStatusStorage"
            return config

        # Check Hybrid (Redis + others)
        if config.redis_uri:
            config.mode = StorageMode.HYBRID
            config.kv_storage = "RedisKVStorage"
            config.doc_status_storage = "RedisDocStatusStorage"
            # Vector and Graph can be customized
            if config.milvus_uri:
                config.vector_storage = "MilvusVectorDBStorage"
            if config.neo4j_uri:
                config.graph_storage = "Neo4JStorage"
            return config

        # Default: Local mode
        config.mode = StorageMode.LOCAL
        return config

    def ensure_dirs(self) -> None:
        """Create all directories if they don't exist."""
        self.lightrag_dir.mkdir(parents=True, exist_ok=True)
        self.hypergraph_dir.mkdir(parents=True, exist_ok=True)
        self.viz_dir.mkdir(parents=True, exist_ok=True)

    def get_hypergraph_db_path(self) -> Path:
        """Get full path to SQLite hypergraph database."""
        return self.hypergraph_dir / self.hypergraph_db

    def to_lightrag_kwargs(self) -> dict[str, str]:
        """Get kwargs for LightRAG initialization."""
        return {
            "kv_storage": self.kv_storage,
            "vector_storage": self.vector_storage,
            "graph_storage": self.graph_storage,
            "doc_status_storage": self.doc_status_storage,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "kv_storage": self.kv_storage,
            "vector_storage": self.vector_storage,
            "graph_storage": self.graph_storage,
            "lightrag_dir": str(self.lightrag_dir),
            "hypergraph_dir": str(self.hypergraph_dir),
        }


@dataclass
class MCPConfig:
    """MCP Server specific configuration."""

    # Internal LLM for automated tasks (entity extraction, memory evolution)
    # This runs independently of the external MCP client (Claude/GPT)
    internal_llm_enabled: bool = field(
        default_factory=lambda: os.getenv("MCP_INTERNAL_LLM_ENABLED", "true").lower() == "true"
    )
    internal_llm_provider: Literal["ollama", "openai", "none"] = field(
        default_factory=lambda: os.getenv("MCP_INTERNAL_LLM_PROVIDER", "ollama")  # type: ignore
    )
    internal_llm_model: str = field(
        default_factory=lambda: os.getenv("MCP_INTERNAL_LLM_MODEL", "qwen2:7b")
    )
    internal_llm_host: str = field(
        default_factory=lambda: os.getenv("MCP_INTERNAL_LLM_HOST", "http://localhost:11434")
    )

    # Feature flags
    auto_collect_entities: bool = True  # Auto-fill missing entities in KG
    auto_evolve_memory: bool = True  # Auto-evolve memory after queries

    # Session management (for multi-user)
    enable_sessions: bool = True
    session_timeout: int = 3600  # 1 hour

    # Rate limiting
    max_requests_per_minute: int = 60

    def get_internal_llm_func(self) -> Callable | None:
        """Get the internal LLM function for automated tasks."""
        if not self.internal_llm_enabled or self.internal_llm_provider == "none":
            return None

        if self.internal_llm_provider == "ollama":
            return get_ollama_llm_func(host=self.internal_llm_host, model=self.internal_llm_model)
        elif self.internal_llm_provider == "openai":
            # Use OpenAI for internal tasks
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None

            async def openai_internal_llm(prompt: str, **kwargs: Any) -> str:
                from lightrag.llm.openai import openai_complete_if_cache

                res = await openai_complete_if_cache(
                    model=self.internal_llm_model, prompt=prompt, **kwargs
                )
                return cast(str, res)

            return openai_internal_llm

        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "internal_llm_enabled": self.internal_llm_enabled,
            "internal_llm_provider": self.internal_llm_provider,
            "internal_llm_model": self.internal_llm_model,
            "auto_collect_entities": self.auto_collect_entities,
            "auto_evolve_memory": self.auto_evolve_memory,
            "enable_sessions": self.enable_sessions,
        }


@dataclass
class HyperHierarchicalConfig:
    """Main configuration container."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)

    # Feature flags
    enable_hypergraph: bool = True
    enable_memory_evolution: bool = True
    enable_visualization: bool = True

    # Query settings
    default_top_k: int = 10
    max_hypergraph_hops: int = 2

    @classmethod
    def from_env(cls) -> "HyperHierarchicalConfig":
        """Load configuration from environment variables."""
        config = cls()

        # Override from env with type checking
        llm_provider = os.getenv("LLM_PROVIDER")
        if llm_provider in ("openai", "ollama", "azure"):
            config.llm.provider = llm_provider  # type: ignore

        llm_model = os.getenv("LLM_MODEL")
        if llm_model:
            config.llm.model = llm_model

        embed_provider = os.getenv("EMBEDDING_PROVIDER")
        if embed_provider in ("openai", "sentence-transformers", "ollama"):
            config.embedding.provider = embed_provider  # type: ignore

        # Auto-detect storage mode
        config.storage = StorageConfig.auto_detect()

        # Ensure directories exist
        config.storage.ensure_dirs()

        return config

    def validate(self) -> dict[str, Any]:
        """Validate configuration and return status."""
        issues = []

        if not self.llm.validate():
            issues.append("LLM API key not configured")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "llm": self.llm.to_dict(),
            "embedding": self.embedding.to_dict(),
            "storage": self.storage.to_dict(),
            "mcp": self.mcp.to_dict(),
        }


# Global configuration instance
_config: HyperHierarchicalConfig | None = None


def get_config() -> HyperHierarchicalConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = HyperHierarchicalConfig.from_env()
    return _config


def set_config(config: HyperHierarchicalConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
