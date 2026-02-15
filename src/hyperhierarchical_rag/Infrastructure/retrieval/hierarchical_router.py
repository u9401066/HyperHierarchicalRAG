"""
HierarchicalRouter - Adapter wrapping LightRAG's hierarchical keyword extraction.

This module adapts LightRAG's dual-level keyword system:
- ll_keywords (Local): Entity-level keywords for precise retrieval
- hl_keywords (Global): Theme-level keywords for semantic retrieval

References:
- LightRAG: https://github.com/HKUDS/LightRAG
- lightrag-mcp: https://github.com/shemhamforash23/lightrag-mcp
"""

import logging
from typing import Any

from lightrag import LightRAG, QueryParam

logger = logging.getLogger(__name__)


class HierarchicalRouter:
    """
    Adapter for LightRAG's hierarchical retrieval.

    Provides:
    - Local keyword extraction (ll_keywords)
    - Global keyword extraction (hl_keywords)
    - Query routing based on keyword level

    Usage:
        router = HierarchicalRouter(working_dir="./data")
        local_kw = await router.extract_local_keywords("What is propofol?")
        global_kw = await router.extract_global_keywords("Discuss anesthesia trends")
    """

    def __init__(
        self,
        working_dir: str = "./data/lightrag",
        llm_model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        """
        Initialize HierarchicalRouter with LightRAG backend.

        Args:
            working_dir: Directory for LightRAG data storage
            llm_model: LLM model for keyword extraction
            embedding_model: Embedding model for semantic search
        """
        self.working_dir = working_dir
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self._rag: LightRAG | None = None
        logger.info(f"HierarchicalRouter initialized (working_dir={working_dir})")

    async def initialize(self) -> None:
        """Initialize the LightRAG instance (lazy initialization)."""
        if self._rag is not None:
            return

        try:
            # Import LightRAG components
            from lightrag import LightRAG
            from lightrag.llm.openai import openai_complete_if_cache, openai_embed

            self._rag = LightRAG(
                working_dir=self.working_dir,
                llm_model_func=openai_complete_if_cache,
                embedding_func=openai_embed,
            )
            logger.info("LightRAG instance initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize LightRAG: {e}")
            self._rag = None

    async def extract_local_keywords(self, query: str) -> list[str]:
        """
        Extract local (entity-level) keywords from query.

        These correspond to LightRAG's ll_keywords - specific entities,
        names, technical terms that need precise matching.

        Args:
            query: Query text

        Returns:
            List of local keywords
        """
        await self.initialize()

        if self._rag is None:
            # Fallback to simple extraction
            return self._simple_keyword_extract(query, level="local")

        try:
            # Use LightRAG's keyword extraction
            # Reference: lightrag/kg/keyword_extractor.py
            keywords = await self._extract_keywords_via_lightrag(query, level="local")
            return keywords
        except Exception as e:
            logger.warning(f"LightRAG extraction failed: {e}, using fallback")
            return self._simple_keyword_extract(query, level="local")

    async def extract_global_keywords(self, query: str) -> list[str]:
        """
        Extract global (theme-level) keywords from query.

        These correspond to LightRAG's hl_keywords - abstract concepts,
        themes, topics that benefit from semantic matching.

        Args:
            query: Query text

        Returns:
            List of global keywords
        """
        await self.initialize()

        if self._rag is None:
            return self._simple_keyword_extract(query, level="global")

        try:
            keywords = await self._extract_keywords_via_lightrag(query, level="global")
            return keywords
        except Exception as e:
            logger.warning(f"LightRAG extraction failed: {e}, using fallback")
            return self._simple_keyword_extract(query, level="global")

    async def extract_both_levels(self, query: str) -> tuple[list[str], list[str]]:
        """
        Extract both local and global keywords.

        Returns:
            Tuple of (local_keywords, global_keywords)
        """
        local_kw = await self.extract_local_keywords(query)
        global_kw = await self.extract_global_keywords(query)
        return local_kw, global_kw

    async def route_query(
        self,
        query: str,
        mode: str = "hybrid",
    ) -> dict[str, Any]:
        """
        Route query based on keyword analysis.

        Modes:
        - "local": Use only local keywords (precise entity search)
        - "global": Use only global keywords (semantic theme search)
        - "hybrid": Use both levels (recommended)

        Args:
            query: Query text
            mode: Routing mode

        Returns:
            Routing decision with keywords and recommended strategy
        """
        local_kw, global_kw = await self.extract_both_levels(query)

        # Analyze query characteristics
        has_entities = len(local_kw) > 0
        has_themes = len(global_kw) > 0

        if mode == "local":
            strategy = "entity_search"
        elif mode == "global":
            strategy = "semantic_search"
        else:  # hybrid
            if has_entities and has_themes:
                strategy = "hybrid_search"
            elif has_entities:
                strategy = "entity_search"
            elif has_themes:
                strategy = "semantic_search"
            else:
                strategy = "fallback_search"

        return {
            "query": query,
            "mode": mode,
            "local_keywords": local_kw,
            "global_keywords": global_kw,
            "strategy": strategy,
            "has_entities": has_entities,
            "has_themes": has_themes,
        }

    async def insert_text(self, text: str) -> dict[str, Any]:
        """
        Insert text into LightRAG for indexing.

        This builds the knowledge graph that powers keyword extraction.
        """
        await self.initialize()

        if self._rag is None:
            return {"status": "error", "message": "LightRAG not initialized"}

        try:
            await self._rag.ainsert(text)
            return {"status": "success", "message": "Text indexed"}
        except Exception as e:
            logger.error(f"Failed to insert text: {e}")
            return {"status": "error", "message": str(e)}

    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
    ) -> dict[str, Any]:
        """
        Execute a query using LightRAG.

        Args:
            query: Query text
            mode: Search mode (local, global, hybrid, naive)
            top_k: Number of results

        Returns:
            Query results from LightRAG
        """
        await self.initialize()

        if self._rag is None:
            return {"status": "error", "message": "LightRAG not initialized"}

        try:
            param = QueryParam(mode=mode, top_k=top_k)
            result = await self._rag.aquery(query, param=param)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {"status": "error", "message": str(e)}

    # ==================== Private Methods ====================

    async def _extract_keywords_via_lightrag(
        self,
        query: str,
        level: str,
    ) -> list[str]:
        """Extract keywords using LightRAG's internal methods."""
        # This would use LightRAG's keyword extraction
        # For now, use simple extraction as placeholder
        return self._simple_keyword_extract(query, level)

    def _simple_keyword_extract(self, query: str, level: str) -> list[str]:
        """
        Simple keyword extraction fallback.

        Local: Extract proper nouns, technical terms
        Global: Extract abstract concepts, verbs
        """
        import re

        words = query.lower().split()

        if level == "local":
            # Local: longer words, likely entities
            keywords = [w for w in words if len(w) > 4 and w.isalpha()]
            # Also extract capitalized words (proper nouns) from original
            proper_nouns = re.findall(r"\b[A-Z][a-z]+\b", query)
            keywords.extend([n.lower() for n in proper_nouns])
            return list(set(keywords))[:10]
        else:  # global
            # Global: common theme words
            theme_indicators = [
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
            themes = [w for w in words if w in theme_indicators]
            # If no explicit themes, use verbs
            if not themes:
                themes = [w for w in words if len(w) > 5]
            return list(set(themes))[:5]
