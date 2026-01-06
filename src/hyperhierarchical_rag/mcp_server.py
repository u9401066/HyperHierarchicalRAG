"""
MCP Server for HyperHierarchicalRAG

Exposes RAG capabilities as MCP tools for AI Agent integration.
Inspired by: https://github.com/shemhamforash23/lightrag-mcp

Tools provided:
- Document CRUD: insert_document, get_documents, delete_document
- Knowledge Query: query_hybrid, query_local, query_global
- Graph Operations: create_entities, create_relations, evolve_memory
- System: get_health, get_pipeline_status
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, AsyncIterator

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from hyperhierarchical_rag.Domain.entities import HyperNode, HyperEdge, NodeLevel
from hyperhierarchical_rag.Application.query_processor import QueryProcessor
from hyperhierarchical_rag.Application.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Application context with typed resources."""
    query_processor: QueryProcessor
    memory_manager: MemoryManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manages application lifecycle.
    Initializes QueryProcessor and MemoryManager at startup.
    """
    query_processor = QueryProcessor()
    memory_manager = MemoryManager()
    
    logger.info("HyperHierarchicalRAG MCP Server starting...")
    
    try:
        yield AppContext(
            query_processor=query_processor,
            memory_manager=memory_manager,
        )
    finally:
        logger.info("HyperHierarchicalRAG MCP Server stopped")


# Initialize MCP Server
mcp = FastMCP("HyperHierarchicalRAG MCP Server", lifespan=app_lifespan)


def format_response(result: Any, is_error: bool = False) -> Dict[str, Any]:
    """Format response in standard format."""
    if is_error:
        return {"status": "error", "error": str(result)}
    
    if isinstance(result, dict):
        return {"status": "success", "response": result}
    if hasattr(result, "to_dict"):
        return {"status": "success", "response": result.to_dict()}
    
    return {"status": "success", "response": str(result)}


# ==================== Document CRUD Tools ====================

@mcp.tool(
    name="insert_document",
    description="Insert a document into the RAG system. Extracts entities and relations automatically."
)
async def insert_document(
    ctx: Context,
    text: str = Field(description="Document text to insert"),
    doc_id: Optional[str] = Field(description="Optional document ID", default=None),
    metadata: Optional[Dict[str, Any]] = Field(description="Optional metadata", default=None),
) -> Dict[str, Any]:
    """Insert a document and extract knowledge graph."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.memory_manager.insert_document(
            text=text,
            doc_id=doc_id,
            metadata=metadata or {},
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error inserting document: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="get_documents",
    description="Get list of all documents in the RAG system."
)
async def get_documents(ctx: Context) -> Dict[str, Any]:
    """Get all documents."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.memory_manager.get_documents()
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error getting documents: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="delete_document",
    description="Delete a document and its associated entities/relations."
)
async def delete_document(
    ctx: Context,
    doc_id: str = Field(description="Document ID to delete"),
) -> Dict[str, Any]:
    """Delete a document."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.memory_manager.delete_document(doc_id=doc_id)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error deleting document: {e}")
        return format_response(str(e), is_error=True)


# ==================== Knowledge Query Tools ====================

@mcp.tool(
    name="query_hybrid",
    description="Execute a hybrid query combining hierarchical retrieval and hypergraph reasoning."
)
async def query_hybrid(
    ctx: Context,
    query: str = Field(description="Query text"),
    top_k: int = Field(description="Number of results", default=10),
    use_hypergraph: bool = Field(description="Enable hypergraph reasoning", default=True),
) -> Dict[str, Any]:
    """Hybrid query with hierarchical + hypergraph."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.query_processor.query_hybrid(
            query=query,
            top_k=top_k,
            use_hypergraph=use_hypergraph,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error in hybrid query: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="query_local",
    description="Execute a local (entity-level) keyword query."
)
async def query_local(
    ctx: Context,
    query: str = Field(description="Query text"),
    top_k: int = Field(description="Number of results", default=10),
) -> Dict[str, Any]:
    """Local keyword query (ll_keywords in LightRAG)."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.query_processor.query_local(
            query=query,
            top_k=top_k,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error in local query: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="query_global",
    description="Execute a global (theme-level) semantic query."
)
async def query_global(
    ctx: Context,
    query: str = Field(description="Query text"),
    top_k: int = Field(description="Number of results", default=10),
) -> Dict[str, Any]:
    """Global semantic query (hl_keywords in LightRAG)."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.query_processor.query_global(
            query=query,
            top_k=top_k,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error in global query: {e}")
        return format_response(str(e), is_error=True)


# ==================== Graph Operations Tools ====================

@mcp.tool(
    name="create_entities",
    description="Create multiple entities in the knowledge graph."
)
async def create_entities(
    ctx: Context,
    entities: List[Dict[str, Any]] = Field(
        description="""
        List of entity dictionaries:
        - name (str): Entity name
        - description (str): Entity description
        - level (str): 'local' or 'global'
        - keywords (list): Keywords for indexing
        """
    ),
) -> Dict[str, Any]:
    """Create entities in the hypergraph."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.memory_manager.create_entities(entities)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error creating entities: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="create_relations",
    description="Create hyperedges (n-ary relations) between entities."
)
async def create_relations(
    ctx: Context,
    relations: List[Dict[str, Any]] = Field(
        description="""
        List of relation dictionaries:
        - node_ids (list): List of entity IDs to connect
        - relation (str): Relation type
        - context (str): Text context
        - weight (float): Relation strength (0-1)
        """
    ),
) -> Dict[str, Any]:
    """Create hyperedges in the graph."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.memory_manager.create_relations(relations)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error creating relations: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="evolve_memory",
    description="Trigger memory evolution on the hypergraph (from HGMem)."
)
async def evolve_memory(
    ctx: Context,
    query: Optional[str] = Field(description="Query to guide evolution", default=None),
    decay_unused: bool = Field(description="Decay unused edges", default=True),
) -> Dict[str, Any]:
    """Evolve the hypergraph memory."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.memory_manager.evolve(
            query=query,
            decay_unused=decay_unused,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error evolving memory: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="get_graph_stats",
    description="Get statistics about the knowledge graph."
)
async def get_graph_stats(ctx: Context) -> Dict[str, Any]:
    """Get graph statistics."""
    try:
        app_ctx: AppContext = ctx.request_context.lifespan_context
        result = await app_ctx.memory_manager.get_graph_stats()
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error getting graph stats: {e}")
        return format_response(str(e), is_error=True)


# ==================== System Tools ====================

@mcp.tool(
    name="get_health",
    description="Check the health status of the RAG system."
)
async def get_health(ctx: Context) -> Dict[str, Any]:
    """Health check."""
    return format_response({
        "status": "healthy",
        "version": "0.1.0",
        "components": {
            "hierarchical_router": "ok",
            "hypergraph_memory": "ok",
            "persistence": "ok",
        }
    })


def main() -> None:
    """Entry point for MCP server."""
    import sys
    mcp.run()


if __name__ == "__main__":
    main()
