"""
Configuration for HyperHierarchicalRAG

Centralized configuration for LLM, KG, and system settings.
Uses environment variables with sensible defaults.

INTEGRATION: Uses LightRAG's built-in Ollama support when provider="ollama"
- LLM: lightrag.llm.ollama.ollama_model_complete
- Embedding: lightrag.llm.ollama.ollama_embed
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional

from dotenv import load_dotenv

# Load .env file
load_dotenv()


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
    except ImportError:
        raise ImportError(
            "LightRAG not installed. Run: uv pip install -e ./external/LightRAG"
        )


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
        
        async def embed_func(texts: List[str]) -> List[List[float]]:
            result = await ollama_embed(
                texts=texts,
                host=host,
                embed_model=model,
            )
            # Convert numpy array to list if needed
            if hasattr(result, 'tolist'):
                return result.tolist()  # type: ignore
            return list(result)
        return embed_func
    except ImportError:
        raise ImportError(
            "LightRAG not installed. Run: uv pip install -e ./external/LightRAG"
        )


@dataclass
class LLMConfig:
    """LLM configuration."""
    
    provider: Literal["openai", "ollama", "azure"] = "openai"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    api_base: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_BASE"))
    temperature: float = 0.0
    max_tokens: int = 4096
    
    # Ollama settings
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    
    def validate(self) -> bool:
        """Check if configuration is valid."""
        if self.provider == "openai" and not self.api_key:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_base": self.api_base,
            "temperature": self.temperature,
            "has_api_key": bool(self.api_key),
        }


@dataclass
class EmbeddingConfig:
    """Embedding model configuration."""
    
    provider: Literal["openai", "sentence-transformers", "ollama"] = "openai"
    model: str = "text-embedding-3-small"
    dimension: int = 1536
    
    # Sentence Transformers settings
    st_model: str = "all-MiniLM-L6-v2"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "dimension": self.dimension,
        }


@dataclass
class StorageConfig:
    """Storage configuration."""
    
    # LightRAG storage
    lightrag_dir: Path = field(default_factory=lambda: Path("./data/lightrag"))
    
    # Hypergraph storage
    hypergraph_dir: Path = field(default_factory=lambda: Path("./data/hypergraph"))
    
    # Neo4j (optional)
    neo4j_uri: Optional[str] = field(default_factory=lambda: os.getenv("NEO4J_URI"))
    neo4j_user: Optional[str] = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: Optional[str] = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD"))
    
    # Visualization output
    viz_dir: Path = field(default_factory=lambda: Path("./data/visualizations"))
    
    def ensure_dirs(self) -> None:
        """Create all directories if they don't exist."""
        self.lightrag_dir.mkdir(parents=True, exist_ok=True)
        self.hypergraph_dir.mkdir(parents=True, exist_ok=True)
        self.viz_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class HyperHierarchicalConfig:
    """Main configuration container."""
    
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    
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
        
        # Ensure directories exist
        config.storage.ensure_dirs()
        
        return config
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return status."""
        issues = []
        
        if not self.llm.validate():
            issues.append("LLM API key not configured")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "llm": self.llm.to_dict(),
            "embedding": self.embedding.to_dict(),
        }


# Global configuration instance
_config: Optional[HyperHierarchicalConfig] = None


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
