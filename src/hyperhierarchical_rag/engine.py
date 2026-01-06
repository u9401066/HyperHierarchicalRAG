"""
RAG Engine - Complete integration of LightRAG + HGMem with visualization

This is the main entry point that properly initializes:
1. LLM backend (OpenAI, Ollama, etc.)
2. LightRAG Knowledge Graph (直接使用，不重造輪子！)
3. HGMem Memory Evolution (整合到查詢流程)
4. Visualization

關鍵原則：
- LightRAG 已有的功能直接用 (KG, VDB, Query)
- HGMem 的記憶演化整合到查詢流程中
- Adapters 只是包裝層，讓 HGMem 組件能操作 LightRAG 存儲

Usage:
    from hyperhierarchical_rag import RAGEngine
    
    engine = RAGEngine.from_env()  # Load config from .env
    await engine.initialize()
    
    # Insert documents
    await engine.insert("Propofol is used for sedation in ICU...")
    
    # Query with memory evolution
    result = await engine.query("Compare propofol and remimazolam", evolve_memory=True)
"""

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Set

# Type alias for LightRAG query modes
QueryMode = Literal['local', 'global', 'hybrid', 'naive', 'mix', 'bypass']

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

# Import Adapters
from hyperhierarchical_rag.Infrastructure.adapters import (
    LightRAGKGAdapter,
    VectorStoreAdapter,
)
from hyperhierarchical_rag.Infrastructure.adapters.vector_store_adapter import TextChunksAdapter
from hyperhierarchical_rag.Domain.services import (
    EnhancedMemoryEvolver,
    KGMemorySyncService,
    MemoryPointwiseRetriever,
    MemoryQueryParam,
)

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Main RAG Engine integrating LightRAG + HGMem.
    
    Features:
    - Automatic LLM/KG initialization
    - Hybrid query (hierarchical + hypergraph)
    - Memory evolution with automatic entity completion
    - Query path visualization
    
    關鍵設計:
    - LightRAG 處理: 文檔索引、KG 構建、基本查詢
    - HGMem 處理: 記憶演化、缺失實體補全、上下文擴展
    - Adapters: 讓 HGMem 組件能操作 LightRAG 存儲
    
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                        RAGEngine Architecture                          ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                        ║
    ║  ┌─────────────────────────────────────────────────────────────────┐  ║
    ║  │                         RAGEngine                                │  ║
    ║  │                                                                  │  ║
    ║  │  ┌─────────────────────────────────────────────────────────┐   │  ║
    ║  │  │           LightRAG (直接使用，不重造！)                    │   │  ║
    ║  │  │  • entities_vdb    • relationships_vdb   • chunks_vdb   │   │  ║
    ║  │  │  • chunk_entity_relation_graph  • text_chunks           │   │  ║
    ║  │  │  • aquery() / ainsert()                                 │   │  ║
    ║  │  └──────────────────────┬──────────────────────────────────┘   │  ║
    ║  │                         │ Adapters (包裝層)                     │  ║
    ║  │  ┌──────────────────────▼──────────────────────────────────┐   │  ║
    ║  │  │              HGMem Integration                           │   │  ║
    ║  │  │  • EnhancedMemoryEvolver (記憶演化)                       │   │  ║
    ║  │  │  • KGMemorySyncService (缺失實體補全)                     │   │  ║
    ║  │  │  • MemoryPointwiseRetriever (記憶點檢索)                  │   │  ║
    ║  │  └─────────────────────────────────────────────────────────┘   │  ║
    ║  │                                                                  │  ║
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
        self._lightrag: Any = None  # LightRAG instance
        self._llm_func: Optional[Callable] = None
        
        # LightRAG Adapters (wrap LightRAG components for HGMem)
        self._kg_adapter: Optional[LightRAGKGAdapter] = None
        self._entities_vdb: Optional[VectorStoreAdapter] = None
        self._relationships_vdb: Optional[VectorStoreAdapter] = None
        self._chunks_vdb: Optional[VectorStoreAdapter] = None
        self._text_chunks_adapter: Optional[TextChunksAdapter] = None
        
        # HGMem components
        self._memory_evolver: Optional[EnhancedMemoryEvolver] = None
        self._sync_service: Optional[KGMemorySyncService] = None
        self._memory_retriever: Optional[MemoryPointwiseRetriever] = None
        
        # Application layer (backward compatibility)
        self._query_processor: Optional[QueryProcessor] = None
        self._memory_manager: Optional[MemoryManager] = None
        
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
        
        This is where LLM, LightRAG, and HGMem components are actually started!
        
        Returns:
            Status dict with initialization results
        """
        if self._initialized:
            return {"status": "already_initialized"}
        
        status: Dict[str, Any] = {"status": "initializing", "components": {}}
        
        # 1. Initialize LLM
        try:
            self._llm_func = await self._init_llm()
            status["components"]["llm"] = "ok"
        except Exception as e:
            logger.error(f"LLM initialization failed: {e}")
            status["components"]["llm"] = f"error: {e}"
        
        # 2. Initialize LightRAG (核心！)
        try:
            self._lightrag = await self._init_lightrag()
            status["components"]["lightrag"] = "ok"
            
            # 3. Create Adapters (包裝 LightRAG 組件給 HGMem 用)
            await self._init_adapters()
            status["components"]["adapters"] = "ok"
            
            # 4. Create HGMem services
            await self._init_hgmem_services()
            status["components"]["hgmem"] = "ok"
            
        except Exception as e:
            logger.warning(f"LightRAG/HGMem initialization failed: {e}")
            status["components"]["lightrag"] = f"error: {e}"
        
        # 5. Initialize Application layer (backward compatibility)
        self._query_processor = QueryProcessor(llm_func=self._llm_func)
        self._memory_manager = MemoryManager()
        
        # Share state between processor and manager
        if self._query_processor and self._memory_manager:
            self._query_processor._nodes = self._memory_manager._nodes
            self._query_processor._edges = self._memory_manager._edges
        
        status["components"]["query_processor"] = "ok"
        status["components"]["memory_manager"] = "ok"
        
        # 6. Initialize Visualization
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
    
    async def _init_adapters(self) -> None:
        """Initialize Adapters that wrap LightRAG components."""
        if not self._lightrag:
            raise RuntimeError("LightRAG must be initialized before adapters")
        
        # KG Adapter - wraps LightRAG's knowledge graph
        self._kg_adapter = LightRAGKGAdapter(
            self._lightrag.chunk_entity_relation_graph
        )
        
        # Vector Store Adapters - wrap LightRAG's vector databases
        self._entities_vdb = VectorStoreAdapter(
            self._lightrag.entities_vdb,
            namespace="entities"
        )
        self._relationships_vdb = VectorStoreAdapter(
            self._lightrag.relationships_vdb,
            namespace="relationships"
        )
        self._chunks_vdb = VectorStoreAdapter(
            self._lightrag.chunks_vdb,
            namespace="chunks"
        )
        
        # Text Chunks Adapter - combines KV storage + vector search
        self._text_chunks_adapter = TextChunksAdapter(
            kv_storage=self._lightrag.text_chunks,
            vector_storage=self._lightrag.chunks_vdb
        )
        
        logger.info("Adapters initialized (wrapping LightRAG components)")
    
    async def _init_hgmem_services(self) -> None:
        """Initialize HGMem services using adapters."""
        if not self._llm_func:
            logger.warning("LLM not available, HGMem services limited")
            return
        
        # Memory Evolver - handles memory evolution
        self._memory_evolver = EnhancedMemoryEvolver(
            llm_func=self._llm_func
        )
        
        # KG-Memory Sync Service - auto-completes missing entities
        if self._kg_adapter and self._entities_vdb and self._relationships_vdb:
            self._sync_service = KGMemorySyncService(
                kg_adapter=self._kg_adapter,
                entities_vdb=self._entities_vdb,
                relationships_vdb=self._relationships_vdb,
                llm_func=self._llm_func
            )
        
        # Memory Pointwise Retriever
        if self._kg_adapter and self._text_chunks_adapter:
            self._memory_retriever = MemoryPointwiseRetriever(
                kg_adapter=self._kg_adapter,
                text_chunks_adapter=self._text_chunks_adapter
            )
        
        logger.info("HGMem services initialized")
    
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
        
        Uses LightRAG directly - no need to reinvent the wheel!
        LightRAG handles: chunking, entity extraction, KG building, vector indexing.
        """
        self._ensure_initialized()
        
        result: Dict[str, Any] = {"doc_id": doc_id, "lightrag": None}
        
        # Insert into LightRAG (handles everything!)
        if self._lightrag:
            try:
                await self._lightrag.ainsert(text)
                result["lightrag"] = "indexed"
                logger.info(f"Document indexed in LightRAG: {doc_id or 'anonymous'}")
            except Exception as e:
                logger.error(f"LightRAG insert failed: {e}")
                result["lightrag"] = f"error: {e}"
        else:
            result["lightrag"] = "not_available"
        
        return result
    
    # ==================== Query Operations ====================
    
    async def query(
        self,
        query: str,
        mode: QueryMode = "hybrid",
        top_k: int = 10,
        evolve_memory: bool = True,
        visualize: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a query with optional memory evolution.
        
        流程:
        1. LightRAG 查詢 (獲取 KG + 文本塊上下文)
        2. (可選) 記憶演化 (HGMem)
        3. (可選) 缺失實體補全 (HGMem)
        4. (可選) 記憶點相關上下文檢索 (HGMem)
        
        Args:
            query: Query text
            mode: Query mode (local, global, hybrid, naive, mix, bypass)
            top_k: Number of results
            evolve_memory: Enable HGMem memory evolution
            visualize: Generate visualization of query path
        
        Returns:
            Query results with optional memory context
        """
        self._ensure_initialized()
        
        result: Dict[str, Any] = {
            "query": query,
            "mode": mode,
            "lightrag_response": None,
            "memory_context": None,
        }
        
        # Start trace for visualization
        trace = QueryTrace(query=query, mode=mode)
        
        # ========== Step 1: LightRAG Query (直接用！) ==========
        lightrag_response = None
        retrieved_context = ""
        
        if self._lightrag:
            try:
                from lightrag import QueryParam
                param = QueryParam(mode=mode, top_k=top_k)
                lightrag_response = await self._lightrag.aquery(query, param=param)
                retrieved_context = str(lightrag_response) if lightrag_response else ""
                
                trace.add_step(QueryStep(
                    step_number=1,
                    step_type="lightrag_query",
                    description=f"LightRAG {mode} query",
                    keywords=[],
                    level=mode,
                ))
                
                logger.info(f"LightRAG query completed: {len(retrieved_context)} chars")
            except Exception as e:
                logger.warning(f"LightRAG query failed: {e}")
        
        result["lightrag_response"] = lightrag_response
        
        # ========== Step 2: Memory Evolution (HGMem) ==========
        memory_context = None
        absent_entities: Dict[str, List] = {}
        
        if evolve_memory and self._memory_evolver and retrieved_context:
            try:
                # 演化記憶 (使用正確的介面)
                evolve_result = await self._memory_evolver.evolve_and_track(
                    retrieved_info=retrieved_context,
                    main_query=query,
                    subqueries=[],  # 可以在後續加入子查詢支援
                )
                
                # EvolveResult 是 dataclass，使用屬性存取
                inserted_count = len(evolve_result.inserted_points)
                updated_count = len(evolve_result.updated_points)
                
                trace.add_step(QueryStep(
                    step_number=2,
                    step_type="memory_evolution",
                    description=f"Memory evolved: +{inserted_count} inserted, {updated_count} updated",
                    keywords=[],
                ))
                
                logger.info(f"Memory evolution: {inserted_count} inserted, {updated_count} updated")
            except Exception as e:
                logger.warning(f"Memory evolution failed: {e}")
        
        # ========== Step 3: Collect Absent Entities (HGMem) ==========
        if absent_entities and self._sync_service:
            try:
                collected, _ = await self._sync_service.collect_absent_entities_relationships(
                    absent_entities_hyperedges_kv=absent_entities,
                    context_info=retrieved_context
                )
                
                trace.add_step(QueryStep(
                    step_number=3,
                    step_type="entity_completion",
                    description=f"Completed {len(collected)} missing entities",
                    output_node_ids=list(collected.keys())[:5],
                ))
                
                logger.info(f"Entity completion: {len(collected)} entities")
            except Exception as e:
                logger.warning(f"Entity completion failed: {e}")
        
        # ========== Step 4: Get Memory Context (HGMem) ==========
        if self._memory_evolver:
            try:
                memory_context = await self._memory_evolver.get_memory_context()
                result["memory_context"] = memory_context
            except Exception as e:
                logger.warning(f"Get memory context failed: {e}")
        
        # ========== Step 5: Memory Pointwise Retrieval (Optional) ==========
        if self._memory_retriever and self._memory_evolver:
            try:
                # 將 MemoryPoint 轉換為 list[list[str]] 格式
                raw_memory_points = self._memory_evolver.memory_points
                memory_points_list = [p.involved_objects for p in raw_memory_points]
                
                if memory_points_list:
                    retrieval_result = await self._memory_retriever.get_memory_pointwise_related_info(
                        memory_points=memory_points_list,
                        query=query,
                        query_param=MemoryQueryParam()
                    )
                    result["memory_related_info"] = retrieval_result
                    
                    trace.add_step(QueryStep(
                        step_number=4,
                        step_type="memory_retrieval",
                        description=f"Retrieved memory-related chunks",
                        keywords=[],
                    ))
            except Exception as e:
                logger.warning(f"Memory retrieval failed: {e}")
        
        # ========== Finalize ==========
        result["trace"] = trace.to_dict()
        
        # Generate visualization
        if visualize and self._graph_viz and self._memory_manager:
            viz_paths = await self._generate_visualization(trace)
            result["visualization"] = viz_paths
        
        return result
    
    async def query_simple(
        self,
        query: str,
        mode: QueryMode = "hybrid",
    ) -> str:
        """
        Simple query - just returns LightRAG's response.
        
        Use this for quick queries without memory evolution.
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return "LightRAG not available"
        
        try:
            from lightrag import QueryParam
            param = QueryParam(mode=mode)
            response = await self._lightrag.aquery(query, param=param)
            return str(response) if response else "No response"
        except Exception as e:
            return f"Query failed: {e}"
    
    async def _generate_visualization(self, trace: QueryTrace) -> Dict[str, str]:
        """Generate visualization files for query path."""
        paths: Dict[str, str] = {}
        
        # Safety checks
        if not self._memory_manager or not self._graph_viz or not self._path_viz:
            return {"error": "Visualization components not initialized"}
        
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
        
        if not self._memory_manager:
            return {"error": "Memory manager not initialized"}
        
        nodes = list(self._memory_manager._nodes.values())
        edges = list(self._memory_manager._edges.values())
        
        local_nodes = [n for n in nodes if n.level == NodeLevel.LOCAL]
        global_nodes = [n for n in nodes if n.level == NodeLevel.GLOBAL]
        
        # Find cross-level edges (connecting LOCAL and GLOBAL)
        cross_level_edges = []
        for edge in edges:
            levels: Set[NodeLevel] = set()
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
        
        if not self._memory_manager:
            raise RuntimeError("Memory manager not initialized")
        
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
