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
        self._hypergraph_repo: Any = None  # SQLiteHypergraphRepository for persistence
        
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
        
        # Initialize persistence repository for memory points
        from hyperhierarchical_rag.Infrastructure.persistence import SQLiteHypergraphRepository
        
        hypergraph_db_path = self.config.storage.get_hypergraph_db_path()
        self._hypergraph_repo = SQLiteHypergraphRepository(str(hypergraph_db_path))
        
        # Memory Evolver - handles memory evolution with persistence
        self._memory_evolver = EnhancedMemoryEvolver(
            llm_func=self._llm_func,
            persistence_repo=self._hypergraph_repo,
        )
        
        # Load existing memory points from persistence
        loaded_count = await self._memory_evolver.load_from_persistence()
        if loaded_count > 0:
            logger.info(f"Loaded {loaded_count} existing memory points from persistence")
        
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
            # Use internal _ollama_model_if_cache which accepts model directly
            # ollama_model_complete expects hashing_kv in kwargs which we don't have
            from lightrag.llm.ollama import _ollama_model_if_cache
            
            async def llm_func(prompt: str, system_prompt: str = None, **kwargs) -> str:
                # Remove hashing_kv if passed since we're not using LightRAG's cache
                kwargs.pop("hashing_kv", None)
                result = await _ollama_model_if_cache(
                    model=llm_config.model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    host=llm_config.ollama_host,
                    **kwargs
                )
                return result
            
            logger.info(f"LLM initialized: Ollama {llm_config.model}")
            return llm_func
        
        else:
            raise ValueError(f"Unknown LLM provider: {llm_config.provider}")
    
    async def _init_lightrag(self):
        """Initialize LightRAG instance based on LLM provider config."""
        from functools import partial
        from lightrag import LightRAG
        from lightrag.utils import EmbeddingFunc
        
        # Ensure directory exists
        working_dir = str(self.config.storage.lightrag_dir)
        os.makedirs(working_dir, exist_ok=True)
        
        llm_config = self.config.llm
        
        if llm_config.provider == "openai":
            from lightrag.llm.openai import openai_complete_if_cache, openai_embed
            
            rag = LightRAG(
                working_dir=working_dir,
                llm_model_func=openai_complete_if_cache,
                embedding_func=openai_embed,
            )
        elif llm_config.provider == "ollama":
            from lightrag.llm.ollama import ollama_model_complete, ollama_embed
            
            # Get embedding model from config
            embed_model = llm_config.embedding_model
            embed_dim = llm_config.embedding_dim
            
            rag = LightRAG(
                working_dir=working_dir,
                llm_model_func=ollama_model_complete,
                llm_model_name=llm_config.model,
                llm_model_kwargs={
                    "host": llm_config.ollama_host,
                    "options": {"num_ctx": 8192},
                },
                # Use EmbeddingFunc with partial to pass host parameter
                # Reference: lightrag/examples/lightrag_ollama_demo.py
                embedding_func=EmbeddingFunc(
                    embedding_dim=embed_dim,
                    max_token_size=8192,
                    func=partial(
                        ollama_embed.func,  # Access unwrapped function
                        embed_model=embed_model,
                        host=llm_config.ollama_host,
                    ),
                ),
            )
        else:
            raise ValueError(f"Unknown LLM provider for LightRAG: {llm_config.provider}")
        
        # Initialize storages (required for insert operations)
        await rag.initialize_storages()
        
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
        
        # ========== Step 5: Hypergraph Chain Expansion (KEY HGMEM FEATURE!) ==========
        # This is the LONG RAG CHAIN - multi-hop traversal via hyperedges
        expanded_context = ""
        if self._memory_evolver and self._hypergraph_repo:
            try:
                expanded_result = await self._expand_via_hypergraph(
                    query=query,
                    retrieved_context=retrieved_context,
                    max_hops=2,
                )
                expanded_context = expanded_result.get("expanded_context", "")
                
                if expanded_context:
                    result["hypergraph_expanded"] = expanded_result
                    
                    trace.add_step(QueryStep(
                        step_number=5,
                        step_type="hypergraph_expansion",
                        description=f"Hypergraph chain: +{expanded_result.get('new_entities', 0)} entities via {expanded_result.get('hops', 0)}-hop traversal",
                        keywords=expanded_result.get("discovered_entities", [])[:5],
                    ))
                    
                    logger.info(f"Hypergraph expansion: {expanded_result.get('new_entities', 0)} new entities discovered")
            except Exception as e:
                logger.warning(f"Hypergraph expansion failed: {e}")
        
        # ========== Step 6: Memory Pointwise Retrieval (Optional) ==========
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
        if not self._graph_viz or not self._path_viz:
            return {"error": "Visualization components not initialized"}
        
        # 優先使用 LightRAG KG 數據，而非空的 MemoryManager
        nodes, edges = await self._get_visualization_data()
        
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
    
    async def _get_visualization_data(self) -> tuple[List[HyperNode], List[HyperEdge]]:
        """
        Get nodes and edges for visualization.
        
        優先從 LightRAG KG 提取數據，轉換為 HyperNode/HyperEdge 格式。
        """
        nodes: List[HyperNode] = []
        edges: List[HyperEdge] = []
        
        # 嘗試從 LightRAG KG 提取
        if self._lightrag:
            try:
                graph_storage = self._lightrag.chunk_entity_relation_graph
                if hasattr(graph_storage, '_graph'):
                    nx_graph = graph_storage._graph
                    
                    # 轉換 NetworkX nodes 為 HyperNodes
                    for node_id in nx_graph.nodes():
                        node_data = nx_graph.nodes[node_id]
                        hyper_node = HyperNode(
                            name=str(node_id),
                            description=node_data.get('description', ''),
                            level=NodeLevel.LOCAL,  # 預設為 LOCAL
                            keywords=[node_data.get('entity_type', 'entity')],
                            source_id=node_data.get('source_id', ''),
                        )
                        nodes.append(hyper_node)
                    
                    # 轉換 NetworkX edges 為 HyperEdges
                    for src, tgt, edge_data in nx_graph.edges(data=True):
                        hyper_edge = HyperEdge(
                            node_ids={str(src), str(tgt)},
                            relation=edge_data.get('keywords', 'relates_to'),
                            weight=edge_data.get('weight', 1.0),
                            context=edge_data.get('description', ''),
                        )
                        edges.append(hyper_edge)
                    
                    logger.info(f"Extracted {len(nodes)} nodes, {len(edges)} edges from LightRAG KG")
            except Exception as e:
                logger.warning(f"Failed to extract from LightRAG KG: {e}")
        
        # 如果 LightRAG 沒數據，回退到 MemoryManager
        if not nodes and self._memory_manager:
            nodes = list(self._memory_manager._nodes.values())
            edges = list(self._memory_manager._edges.values())
        
        return nodes, edges
    
    async def _expand_via_hypergraph(
        self,
        query: str,
        retrieved_context: str,
        max_hops: int = 2,
    ) -> Dict[str, Any]:
        """
        Expand context via hypergraph traversal (LONG RAG CHAIN - Core HGMem Feature!).
        
        ╔═══════════════════════════════════════════════════════════════════════╗
        ║ HYPERGRAPH CHAIN EXPANSION - Multi-hop Reasoning                      ║
        ╠═══════════════════════════════════════════════════════════════════════╣
        ║                                                                        ║
        ║ LightRAG binary edges:   A ─── B ─── C                                 ║
        ║                         (can only traverse 1 edge at a time)          ║
        ║                                                                        ║
        ║ HGMem hyperedges:   {A, B, C, D} all in one hyperedge                  ║
        ║                         (discovers D even from query about A!)        ║
        ║                                                                        ║
        ║ Example:                                                               ║
        ║   Query: "propofol sedation"                                           ║
        ║   LightRAG finds: Propofol → used_for → Sedation                      ║
        ║   Memory Point: {Propofol, Remimazolam, ICU, Delirium}                ║
        ║   Hypergraph discovers: Remimazolam, Delirium (not in direct path!)  ║
        ║                                                                        ║
        ╚═══════════════════════════════════════════════════════════════════════╝
        
        Args:
            query: Original query text
            retrieved_context: Context from LightRAG
            max_hops: Maximum traversal depth
            
        Returns:
            Dict with expanded_context, discovered_entities, hops used
        """
        result = {
            "expanded_context": "",
            "discovered_entities": [],
            "seed_entities": [],
            "new_entities": 0,
            "hops": 0,
            "memory_points_used": 0,
        }
        
        if not self._memory_evolver or not self._hypergraph_repo:
            return result
        
        # Step 1: Extract seed entities from query and retrieved context
        seed_entities = await self._extract_seed_entities(query, retrieved_context)
        result["seed_entities"] = seed_entities[:10]
        
        if not seed_entities:
            logger.debug("No seed entities found for hypergraph expansion")
            return result
        
        # Step 2: Find memory points containing these seed entities
        related_memory_points = []
        for mp in self._memory_evolver.memory_points:
            mp_entities = set(obj.upper() for obj in mp.involved_objects)
            seed_set = set(e.upper() for e in seed_entities)
            
            # If memory point shares any entity with seeds
            if mp_entities & seed_set:
                related_memory_points.append(mp)
        
        result["memory_points_used"] = len(related_memory_points)
        
        if not related_memory_points:
            logger.debug("No related memory points found")
            return result
        
        # Step 3: Multi-hop expansion via hyperedges (BFS)
        discovered = set()
        seed_set = set(e.upper() for e in seed_entities)
        frontier = seed_set.copy()
        visited = seed_set.copy()
        
        for hop in range(max_hops):
            if not frontier:
                break
            
            next_frontier = set()
            
            for current_entity in frontier:
                # Check all memory points for connections
                for mp in related_memory_points:
                    mp_entities = set(obj.upper() for obj in mp.involved_objects)
                    
                    if current_entity in mp_entities:
                        # Discover all OTHER entities in this hyperedge
                        for entity in mp_entities:
                            if entity not in visited:
                                discovered.add(entity)
                                visited.add(entity)
                                next_frontier.add(entity)
            
            frontier = next_frontier
            result["hops"] = hop + 1
            
            if not next_frontier:
                break
        
        # Step 4: Build expanded context from discovered entities
        discovered_list = list(discovered)
        result["discovered_entities"] = discovered_list
        result["new_entities"] = len(discovered_list)
        
        if discovered_list:
            # Build rich context from memory points containing discovered entities
            context_lines = []
            context_lines.append(f"=== Hypergraph Chain Expansion ({result['hops']}-hop) ===")
            context_lines.append(f"Discovered {len(discovered_list)} additional entities via memory hyperedges:")
            context_lines.append("")
            
            for mp in related_memory_points:
                mp_entities = set(obj.upper() for obj in mp.involved_objects)
                if mp_entities & discovered:
                    context_lines.append(f"• Memory Point: {{{', '.join(mp.involved_objects)}}}")
                    context_lines.append(f"  Description: {mp.description[:200]}")
                    context_lines.append("")
            
            result["expanded_context"] = "\n".join(context_lines)
        
        return result
    
    async def _extract_seed_entities(
        self,
        query: str,
        context: str,
    ) -> List[str]:
        """Extract entity names from query and context for hypergraph expansion."""
        entities = set()
        
        # Method 1: Get entities from LightRAG KG that appear in query/context
        if self._lightrag:
            try:
                graph_storage = self._lightrag.chunk_entity_relation_graph
                if hasattr(graph_storage, '_graph'):
                    nx_graph = graph_storage._graph
                    text_lower = (query + " " + context).lower()
                    
                    for node_id in nx_graph.nodes():
                        node_name = str(node_id).lower()
                        if node_name in text_lower:
                            entities.add(str(node_id))
            except Exception as e:
                logger.debug(f"Entity extraction from KG failed: {e}")
        
        # Method 2: Get entities mentioned in memory points
        if self._memory_evolver:
            for mp in self._memory_evolver.memory_points:
                text_lower = (query + " " + context).lower()
                for obj in mp.involved_objects:
                    if obj.lower() in text_lower:
                        entities.add(obj)
        
        # Method 3: Simple keyword extraction (fallback)
        if not entities:
            import re
            # Extract capitalized words (likely proper nouns/entities)
            proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query + " " + context)
            entities.update(proper_nouns[:10])
        
        return list(entities)[:20]  # Limit to top 20 seeds
    
    # ==================== Graph Operations ====================
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get current graph statistics from LightRAG KG."""
        self._ensure_initialized()
        
        # 從 LightRAG KG 獲取統計
        lightrag_stats = {"nodes": 0, "edges": 0}
        if self._lightrag:
            try:
                graph_storage = self._lightrag.chunk_entity_relation_graph
                if hasattr(graph_storage, '_graph'):
                    nx_graph = graph_storage._graph
                    lightrag_stats["nodes"] = nx_graph.number_of_nodes()
                    lightrag_stats["edges"] = nx_graph.number_of_edges()
            except Exception as e:
                logger.warning(f"Failed to get LightRAG stats: {e}")
        
        # 從 MemoryManager 獲取 HGMem 統計
        hgmem_stats = {"nodes": 0, "edges": 0}
        if self._memory_manager:
            hgmem_stats["nodes"] = len(self._memory_manager._nodes)
            hgmem_stats["edges"] = len(self._memory_manager._edges)
        
        # Memory Evolution 統計
        memory_stats = {"memory_points": 0}
        if self._memory_evolver:
            memory_stats["memory_points"] = len(self._memory_evolver.memory_points)
        
        return {
            "lightrag_kg": lightrag_stats,
            "hgmem_hypergraph": hgmem_stats,
            "memory_evolution": memory_stats,
            "total_entities": lightrag_stats["nodes"] + hgmem_stats["nodes"],
            "total_relations": lightrag_stats["edges"] + hgmem_stats["edges"],
        }
    
    async def generate_visualization(
        self,
        filename: str = "knowledge_graph.html",
        title: str = "HyperHierarchical Knowledge Graph",
    ) -> Dict[str, str]:
        """
        Generate visualization of the current knowledge graph.
        
        直接從 LightRAG KG 生成可視化，不需要執行查詢。
        
        Args:
            filename: Output HTML filename
            title: Graph title
            
        Returns:
            Dict with paths to generated files
        """
        self._ensure_initialized()
        
        if not self._graph_viz:
            return {"error": "Visualization not enabled"}
        
        nodes, edges = await self._get_visualization_data()
        
        if not nodes:
            return {"error": "No data in knowledge graph"}
        
        # Generate HTML visualization
        graph_path = self._graph_viz.to_html(
            nodes=nodes,
            edges=edges,
            title=title,
            filename=filename,
        )
        
        # Also generate JSON export
        json_data = {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }
        }
        json_path = self.config.storage.viz_dir / filename.replace('.html', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Generated visualization: {graph_path}")
        
        return {
            "html": str(graph_path),
            "json": str(json_path),
            "nodes_count": str(len(nodes)),
            "edges_count": str(len(edges)),
        }
    
    # ==================== LightRAG Direct Integration ====================
    # 這些方法直接使用 LightRAG 功能，不重造輪子！
    
    async def insert_custom_kg(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Insert custom knowledge graph data (直接用 LightRAG).
        
        Args:
            entities: List of entity dicts with keys: entity_name, entity_type, description, source_id
            relations: List of relation dicts with keys: src_id, tgt_id, description, keywords, source_id
            
        Returns:
            Insert result
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            await self._lightrag.ainsert_custom_kg(
                custom_kg={
                    "entities": entities,
                    "relationships": relations,
                }
            )
            return {
                "status": "success",
                "entities_count": len(entities),
                "relations_count": len(relations),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def create_entity(
        self,
        entity_name: str,
        entity_type: str = "",
        description: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        """
        Create a single entity in the KG (直接用 LightRAG).
        
        Args:
            entity_name: Name of the entity
            entity_type: Type/category
            description: Entity description
            source_id: Source document ID
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            await self._lightrag.acreate_entity(
                entity_name=entity_name,
                entity_type=entity_type,
                description=description,
                source_id=source_id,
            )
            return {"status": "created", "entity_name": entity_name}
        except Exception as e:
            return {"error": str(e)}
    
    async def create_relation(
        self,
        src_entity: str,
        tgt_entity: str,
        description: str = "",
        keywords: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        """
        Create a relation between entities (直接用 LightRAG).
        
        Args:
            src_entity: Source entity name
            tgt_entity: Target entity name
            description: Relation description
            keywords: Relation keywords
            source_id: Source document ID
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            await self._lightrag.acreate_relation(
                src_entity_name=src_entity,
                tgt_entity_name=tgt_entity,
                description=description,
                keywords=keywords,
                source_id=source_id,
            )
            return {"status": "created", "relation": f"{src_entity} -> {tgt_entity}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_entity_info(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an entity (直接用 LightRAG).
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return None
        
        try:
            return await self._lightrag.get_entity_info(entity_name)
        except Exception:
            return None
    
    async def get_relation_info(
        self, 
        src_entity: str, 
        tgt_entity: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get information about a relation (直接用 LightRAG).
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return None
        
        try:
            return await self._lightrag.get_relation_info(src_entity, tgt_entity)
        except Exception:
            return None
    
    async def get_knowledge_graph(
        self,
        node_label: Optional[str] = None,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Get the knowledge graph structure (直接用 LightRAG).
        
        Args:
            node_label: Filter by node label (entity type)
            max_depth: Maximum traversal depth
            
        Returns:
            Dict with nodes and edges
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            return await self._lightrag.get_knowledge_graph(
                node_label=node_label,
                max_depth=max_depth,
            )
        except Exception as e:
            return {"error": str(e)}
    
    async def delete_by_doc_id(self, doc_id: str) -> Dict[str, Any]:
        """
        Delete all data associated with a document (直接用 LightRAG).
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            await self._lightrag.adelete_by_doc_id(doc_id)
            return {"status": "deleted", "doc_id": doc_id}
        except Exception as e:
            return {"error": str(e)}
    
    async def delete_entity(self, entity_name: str) -> Dict[str, Any]:
        """
        Delete an entity and its relations (直接用 LightRAG).
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            await self._lightrag.adelete_by_entity(entity_name)
            return {"status": "deleted", "entity_name": entity_name}
        except Exception as e:
            return {"error": str(e)}
    
    async def merge_entities(
        self,
        source_entity: str,
        target_entity: str,
    ) -> Dict[str, Any]:
        """
        Merge two entities (直接用 LightRAG).
        
        Args:
            source_entity: Entity to merge from (will be deleted)
            target_entity: Entity to merge into
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            await self._lightrag.amerge_entities(source_entity, target_entity)
            return {"status": "merged", "from": source_entity, "to": target_entity}
        except Exception as e:
            return {"error": str(e)}
    
    async def export_data(self) -> Dict[str, Any]:
        """
        Export all data from LightRAG (直接用 LightRAG).
        
        Returns:
            Dict with entities, relationships, and chunks
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            return await self._lightrag.aexport_data()
        except Exception as e:
            return {"error": str(e)}
    
    async def query_data(
        self,
        query: str,
        mode: QueryMode = "hybrid",
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Query and return raw data instead of LLM response (直接用 LightRAG).
        
        Useful for getting entities, relationships, and chunks without LLM.
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            from lightrag import QueryParam
            param = QueryParam(mode=mode, top_k=top_k)
            return await self._lightrag.aquery_data(query, param=param)
        except Exception as e:
            return {"error": str(e)}
    
    async def clear_cache(self) -> Dict[str, Any]:
        """
        Clear LightRAG's LLM cache (直接用 LightRAG).
        """
        self._ensure_initialized()
        
        if not self._lightrag:
            return {"error": "LightRAG not available"}
        
        try:
            await self._lightrag.aclear_cache()
            return {"status": "cache_cleared"}
        except Exception as e:
            return {"error": str(e)}
    
    # ==================== Visualization ====================
    
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
