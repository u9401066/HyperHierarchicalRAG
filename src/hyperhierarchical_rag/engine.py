"""
RAG Engine - Complete integration of LightRAG + HGMem with visualization

This is the main entry point that properly initializes:
1. LLM backend (OpenAI, Ollama, etc.)
2. LightRAG Knowledge Graph
3. Hypergraph Memory
4. Visualization

Usage:
    from hyperhierarchical_rag import RAGEngine
    
    engine = RAGEngine.from_env()  # Load config from .env
    await engine.initialize()
    
    # Insert documents
    await engine.insert("Propofol is used for sedation in ICU...")
    
    # Query with visualization
    result = await engine.query("Compare propofol and remimazolam", visualize=True)
"""

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from hyperhierarchical_rag.config import (
    HyperHierarchicalConfig, 
    get_config,
    LLMConfig,
)
from hyperhierarchical_rag.Domain.entities import HyperNode, HyperEdge, NodeLevel
from hyperhierarchical_rag.Application.query_processor import QueryProcessor
from hyperhierarchical_rag.Application.memory_manager import MemoryManager
from hyperhierarchical_rag.visualization import HypergraphVisualizer, QueryPathVisualizer
from hyperhierarchical_rag.visualization.query_path_viz import QueryTrace, QueryStep

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Main RAG Engine integrating LightRAG + HGMem.
    
    Features:
    - Automatic LLM/KG initialization
    - Hybrid query (hierarchical + hypergraph)
    - Query path visualization
    - Memory evolution tracking
    
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                        RAGEngine Architecture                          ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                        ║
    ║  ┌─────────────────────────────────────────────────────────────────┐  ║
    ║  │                         RAGEngine                                │  ║
    ║  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐   │  ║
    ║  │  │  LightRAG KG  │  │ QueryProcessor│  │   Visualizer      │   │  ║
    ║  │  │ (hierarchical)│  │ (integration) │  │ (path tracking)   │   │  ║
    ║  │  └───────────────┘  └───────────────┘  └───────────────────┘   │  ║
    ║  │         │                   │                   │               │  ║
    ║  │         └───────────────────┴───────────────────┘               │  ║
    ║  │                             │                                    │  ║
    ║  │                    ┌────────┴────────┐                          │  ║
    ║  │                    │  MemoryManager  │                          │  ║
    ║  │                    │  (hypergraph)   │                          │  ║
    ║  │                    └─────────────────┘                          │  ║
    ║  └─────────────────────────────────────────────────────────────────┘  ║
    ║                                                                        ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, config: Optional[HyperHierarchicalConfig] = None) -> None:
        """
        Initialize RAGEngine.
        
        Args:
            config: Configuration object. If None, loads from environment.
        """
        self.config = config or get_config()
        self._initialized = False
        
        # Core components (initialized lazily)
        self._lightrag = None
        self._query_processor: Optional[QueryProcessor] = None
        self._memory_manager: Optional[MemoryManager] = None
        self._llm_func: Optional[Callable] = None
        
        # Visualization
        self._graph_viz: Optional[HypergraphVisualizer] = None
        self._path_viz: Optional[QueryPathVisualizer] = None
        
        # Query tracing
        self._current_trace: Optional[QueryTrace] = None
        
        logger.info("RAGEngine created (not yet initialized)")
    
    @classmethod
    def from_env(cls) -> "RAGEngine":
        """Create RAGEngine with configuration from environment."""
        config = HyperHierarchicalConfig.from_env()
        return cls(config)
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize all components.
        
        This is where LLM and KG are actually started!
        
        Returns:
            Status dict with initialization results
        """
        if self._initialized:
            return {"status": "already_initialized"}
        
        status = {"status": "initializing", "components": {}}
        
        # 1. Initialize LLM
        try:
            self._llm_func = await self._init_llm()
            status["components"]["llm"] = "ok"
        except Exception as e:
            logger.error(f"LLM initialization failed: {e}")
            status["components"]["llm"] = f"error: {e}"
        
        # 2. Initialize LightRAG
        try:
            self._lightrag = await self._init_lightrag()
            status["components"]["lightrag"] = "ok"
        except Exception as e:
            logger.warning(f"LightRAG initialization failed: {e}")
            status["components"]["lightrag"] = f"error: {e}"
        
        # 3. Initialize Application layer
        self._query_processor = QueryProcessor(llm_func=self._llm_func)
        self._memory_manager = MemoryManager()
        
        # Share state between processor and manager
        self._query_processor._nodes = self._memory_manager._nodes
        self._query_processor._edges = self._memory_manager._edges
        
        status["components"]["query_processor"] = "ok"
        status["components"]["memory_manager"] = "ok"
        
        # 4. Initialize Visualization
        if self.config.enable_visualization:
            self._graph_viz = HypergraphVisualizer(
                output_dir=self.config.storage.viz_dir
            )
            self._path_viz = QueryPathVisualizer(
                output_dir=self.config.storage.viz_dir
            )
            status["components"]["visualization"] = "ok"
        
        self._initialized = True
        status["status"] = "initialized"
        
        logger.info(f"RAGEngine initialized: {status}")
        return status
    
    async def _init_llm(self) -> Callable:
        """Initialize LLM function based on config."""
        llm_config = self.config.llm
        
        if llm_config.provider == "openai":
            if not llm_config.api_key:
                raise ValueError("OPENAI_API_KEY not set")
            
            from lightrag.llm.openai import openai_complete_if_cache
            
            # Create wrapper that uses config
            async def llm_func(prompt: str, **kwargs) -> str:
                return await openai_complete_if_cache(
                    model=llm_config.model,
                    prompt=prompt,
                    **kwargs
                )
            
            logger.info(f"LLM initialized: OpenAI {llm_config.model}")
            return llm_func
        
        elif llm_config.provider == "ollama":
            from lightrag.llm.ollama import ollama_model_complete
            
            async def llm_func(prompt: str, **kwargs) -> str:
                return await ollama_model_complete(
                    model=llm_config.model,
                    prompt=prompt,
                    host=llm_config.ollama_host,
                    **kwargs
                )
            
            logger.info(f"LLM initialized: Ollama {llm_config.model}")
            return llm_func
        
        else:
            raise ValueError(f"Unknown LLM provider: {llm_config.provider}")
    
    async def _init_lightrag(self):
        """Initialize LightRAG instance."""
        from lightrag import LightRAG
        from lightrag.llm.openai import openai_complete_if_cache, openai_embed
        
        # Ensure directory exists
        working_dir = str(self.config.storage.lightrag_dir)
        os.makedirs(working_dir, exist_ok=True)
        
        rag = LightRAG(
            working_dir=working_dir,
            llm_model_func=openai_complete_if_cache,
            embedding_func=openai_embed,
        )
        
        logger.info(f"LightRAG initialized: {working_dir}")
        return rag
    
    # ==================== Document Operations ====================
    
    async def insert(self, text: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Insert a document into the RAG system.
        
        This will:
        1. Index in LightRAG (for hierarchical retrieval)
        2. Extract entities and create hypergraph nodes
        3. Build hyperedges for n-ary relations
        """
        self._ensure_initialized()
        
        result = {"doc_id": doc_id, "lightrag": None, "hypergraph": None}
        
        # 1. Insert into LightRAG
        if self._lightrag:
            try:
                await self._lightrag.ainsert(text)
                result["lightrag"] = "indexed"
            except Exception as e:
                logger.error(f"LightRAG insert failed: {e}")
                result["lightrag"] = f"error: {e}"
        
        # 2. Insert into Hypergraph (via MemoryManager)
        hypergraph_result = await self._memory_manager.insert_document(
            text=text,
            doc_id=doc_id,
        )
        result["hypergraph"] = hypergraph_result
        
        return result
    
    # ==================== Query Operations ====================
    
    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
        use_hypergraph: bool = True,
        evolve_memory: bool = True,
        visualize: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a query with optional visualization.
        
        Args:
            query: Query text
            mode: Query mode (local, global, hybrid)
            top_k: Number of results
            use_hypergraph: Enable hypergraph expansion
            evolve_memory: Enable memory evolution
            visualize: Generate visualization of query path
        
        Returns:
            Query results with optional visualization paths
        """
        self._ensure_initialized()
        
        # Start trace for visualization
        trace = QueryTrace(query=query, mode=mode)
        
        # Step 1: LightRAG query (if available)
        lightrag_result = None
        if self._lightrag and mode in ["local", "global", "hybrid"]:
            try:
                from lightrag import QueryParam
                param = QueryParam(mode=mode, top_k=top_k)
                lightrag_result = await self._lightrag.aquery(query, param=param)
                
                trace.add_step(QueryStep(
                    step_number=1,
                    step_type="lightrag_query",
                    description=f"LightRAG {mode} query",
                    keywords=[],  # Would need to extract from LightRAG
                    level=mode,
                ))
            except Exception as e:
                logger.warning(f"LightRAG query failed: {e}")
        
        # Step 2: Hypergraph query (via QueryProcessor)
        if mode == "hybrid":
            hypergraph_result = await self._query_processor.query_hybrid(
                query=query,
                top_k=top_k,
                use_hypergraph=use_hypergraph,
                evolve_memory=evolve_memory,
            )
        elif mode == "local":
            hypergraph_result = await self._query_processor.query_local(
                query=query,
                top_k=top_k,
            )
        else:
            hypergraph_result = await self._query_processor.query_global(
                query=query,
                top_k=top_k,
            )
        
        # Add hypergraph steps to trace
        trace.add_step(QueryStep(
            step_number=2,
            step_type="keyword_extraction",
            description="Extract Local/Global keywords",
            keywords=hypergraph_result.get("local_keywords", []) + hypergraph_result.get("global_keywords", []),
            level=mode,
        ))
        
        if use_hypergraph:
            trace.add_step(QueryStep(
                step_number=3,
                step_type="hyperedge_traversal",
                description=f"Expand via hyperedges (+{hypergraph_result.get('hypergraph_expanded', 0)} nodes)",
                output_node_ids=[r.get("id", "") for r in hypergraph_result.get("results", [])[:5]],
            ))
        
        trace.total_nodes_visited = hypergraph_result.get("total_candidates", 0)
        trace.local_keywords = hypergraph_result.get("local_keywords", [])
        trace.global_keywords = hypergraph_result.get("global_keywords", [])
        
        # Build result
        result = {
            "query": query,
            "mode": mode,
            "lightrag_response": lightrag_result,
            "hypergraph_response": hypergraph_result,
            "trace": trace.to_dict(),
        }
        
        # Generate visualization
        if visualize and self._graph_viz:
            viz_paths = await self._generate_visualization(trace)
            result["visualization"] = viz_paths
        
        return result
    
    async def _generate_visualization(self, trace: QueryTrace) -> Dict[str, str]:
        """Generate visualization files for query path."""
        paths = {}
        
        # Get current graph state
        nodes = list(self._memory_manager._nodes.values())
        edges = list(self._memory_manager._edges.values())
        
        if not nodes:
            return {"error": "No nodes in graph yet"}
        
        # 1. Full graph HTML
        graph_path = self._graph_viz.to_html(
            nodes=nodes,
            edges=edges,
            title="HyperHierarchicalRAG Knowledge Graph",
            filename="full_graph.html",
        )
        paths["full_graph"] = str(graph_path)
        
        # 2. Query path HTML (with highlighting)
        path_html = self._path_viz.trace_to_html(
            trace=trace,
            nodes=nodes,
            edges=edges,
            filename=f"query_path_{trace.query[:20].replace(' ', '_')}.html",
        )
        paths["query_path"] = str(path_html)
        
        # 3. ASCII trace
        paths["ascii_trace"] = self._path_viz.trace_to_ascii(trace)
        
        # 4. JSON trace
        trace_path = self._path_viz.save_trace(trace)
        paths["trace_json"] = str(trace_path)
        
        return paths
    
    # ==================== Graph Operations ====================
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get current graph statistics."""
        self._ensure_initialized()
        
        nodes = list(self._memory_manager._nodes.values())
        edges = list(self._memory_manager._edges.values())
        
        local_nodes = [n for n in nodes if n.level == NodeLevel.LOCAL]
        global_nodes = [n for n in nodes if n.level == NodeLevel.GLOBAL]
        
        # Find cross-level edges (connecting LOCAL and GLOBAL)
        cross_level_edges = []
        for edge in edges:
            levels = set()
            for node_id in edge.node_ids:
                if node_id in self._memory_manager._nodes:
                    levels.add(self._memory_manager._nodes[node_id].level)
            if len(levels) > 1:
                cross_level_edges.append(edge)
        
        return {
            "nodes": {
                "total": len(nodes),
                "local": len(local_nodes),
                "global": len(global_nodes),
            },
            "edges": {
                "total": len(edges),
                "binary": sum(1 for e in edges if e.is_binary),
                "n_ary": sum(1 for e in edges if not e.is_binary),
                "cross_level": len(cross_level_edges),
            },
            "memory_evolution": {
                "total_evolve_count": sum(e.evolve_count for e in edges),
                "evolved_edges": sum(1 for e in edges if e.evolve_count > 0),
            },
        }
    
    async def visualize_graph(self, filename: str = "graph.html") -> Path:
        """Generate visualization of current graph state."""
        self._ensure_initialized()
        
        if not self._graph_viz:
            raise RuntimeError("Visualization not enabled")
        
        nodes = list(self._memory_manager._nodes.values())
        edges = list(self._memory_manager._edges.values())
        
        return self._graph_viz.to_html(
            nodes=nodes,
            edges=edges,
            title="HyperHierarchicalRAG Graph",
            filename=filename,
        )
    
    # ==================== Utilities ====================
    
    def _ensure_initialized(self) -> None:
        """Ensure engine is initialized."""
        if not self._initialized:
            raise RuntimeError("RAGEngine not initialized. Call initialize() first.")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        return {
            "initialized": self._initialized,
            "config": self.config.validate(),
            "components": {
                "lightrag": self._lightrag is not None,
                "query_processor": self._query_processor is not None,
                "memory_manager": self._memory_manager is not None,
                "visualization": self._graph_viz is not None,
            },
            "graph": self.get_graph_stats() if self._initialized else None,
        }
