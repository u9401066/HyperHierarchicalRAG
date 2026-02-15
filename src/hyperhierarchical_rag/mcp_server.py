"""
MCP Server for HyperHierarchicalRAG (v0.6.0)

Exposes RAG capabilities as MCP tools for AI Agent integration.
Inspired by: https://github.com/shemhamforash23/lightrag-mcp

Tools provided:
═══════════════════════════════════════════════════════════════════════════════
📚 Document CRUD:
  - insert_document: Insert text into RAG system
  - delete_document: Delete document by ID

🔍 Knowledge Query:
  - query: Full query with memory evolution
  - query_simple: Quick query without memory
  - query_data: Get raw entities/relations (no LLM)

🧠 Memory Management:
  - evolve_memory: Trigger memory evolution
  - get_memory_context: Get current memory state
  - clear_memory: Clear all memory points

📊 Knowledge Graph Operations:
  - create_entity: Add single entity
  - create_relation: Add relation between entities
  - get_entity_info: Get entity details
  - get_relation_info: Get relation details
  - get_knowledge_graph: Get full KG structure
  - delete_entity: Remove entity and relations
  - merge_entities: Merge two entities

🔧 System:
  - get_health: Health check
  - get_graph_stats: Graph statistics
  - export_data: Export all data
  - clear_cache: Clear LLM cache
═══════════════════════════════════════════════════════════════════════════════
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from hyperhierarchical_rag.engine import RAGEngine

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Application context with RAGEngine."""

    engine: RAGEngine


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manages application lifecycle.
    Initializes RAGEngine at startup with all components.
    """
    logger.info("HyperHierarchicalRAG MCP Server starting...")

    # Initialize RAGEngine from environment
    engine = RAGEngine.from_env()
    init_result = await engine.initialize()

    logger.info(f"RAGEngine initialized: {init_result}")

    try:
        yield AppContext(engine=engine)
    finally:
        logger.info("HyperHierarchicalRAG MCP Server stopped")


# Initialize MCP Server
mcp = FastMCP("HyperHierarchicalRAG MCP Server", lifespan=app_lifespan)


def format_response(result: Any, is_error: bool = False) -> dict[str, Any]:
    """Format response in standard format."""
    if is_error:
        return {"status": "error", "error": str(result)}

    if isinstance(result, dict):
        return {"status": "success", "response": result}
    if hasattr(result, "to_dict"):
        return {"status": "success", "response": result.to_dict()}

    return {"status": "success", "response": str(result)}


def get_engine(ctx: Context) -> RAGEngine:
    """Helper to get RAGEngine from context."""
    app_ctx: AppContext = ctx.request_context.lifespan_context
    return app_ctx.engine


# ==================== Document CRUD Tools ====================


@mcp.tool(
    name="insert_document",
    description="Insert a document into the RAG system. LightRAG handles: chunking, entity extraction, KG building, vector indexing.",
)
async def insert_document(
    ctx: Context,
    text: str = Field(description="Document text to insert"),
    doc_id: str | None = Field(description="Optional document ID", default=None),
) -> dict[str, Any]:
    """Insert a document and build knowledge graph."""
    try:
        engine = get_engine(ctx)
        result = await engine.insert(text=text, doc_id=doc_id)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error inserting document: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="delete_document",
    description="Delete a document and all its associated entities/relations from the KG.",
)
async def delete_document(
    ctx: Context,
    doc_id: str = Field(description="Document ID to delete"),
) -> dict[str, Any]:
    """Delete a document by ID."""
    try:
        engine = get_engine(ctx)
        result = await engine.delete_by_doc_id(doc_id=doc_id)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error deleting document: {e}")
        return format_response(str(e), is_error=True)


# ==================== Knowledge Query Tools ====================


@mcp.tool(
    name="query",
    description="""Execute a full RAG query with optional memory evolution (HGMem).

Modes:
- hybrid: Combines local (entity-level) + global (theme-level) search (recommended)
- local: Entity/keyword-focused search
- global: Theme/semantic search
- naive: Simple vector search
- mix: All modes combined
- bypass: Skip KG, direct retrieval

Set evolve_memory=True to enable HGMem memory evolution.""",
)
async def query(
    ctx: Context,
    query: str = Field(description="Query text"),
    mode: str = Field(
        description="Query mode: hybrid, local, global, naive, mix, bypass", default="hybrid"
    ),
    top_k: int = Field(description="Number of results to retrieve", default=10),
    evolve_memory: bool = Field(description="Enable HGMem memory evolution", default=True),
    visualize: bool = Field(description="Generate query path visualization", default=False),
) -> dict[str, Any]:
    """Full query with memory evolution."""
    try:
        engine = get_engine(ctx)
        result = await engine.query(
            query=query,
            mode=mode,  # type: ignore
            top_k=top_k,
            evolve_memory=evolve_memory,
            visualize=visualize,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error in query: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="query_simple",
    description="Quick query - returns LightRAG's response without memory evolution. Use for fast lookups.",
)
async def query_simple(
    ctx: Context,
    query: str = Field(description="Query text"),
    mode: str = Field(description="Query mode: hybrid, local, global", default="hybrid"),
) -> dict[str, Any]:
    """Simple query without memory evolution."""
    try:
        engine = get_engine(ctx)
        result = await engine.query_simple(query=query, mode=mode)  # type: ignore
        return format_response({"response": result})
    except Exception as e:
        logger.exception(f"Error in simple query: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="query_data",
    description="Query and return raw entities/relations/chunks without LLM processing. Useful for data exploration.",
)
async def query_data(
    ctx: Context,
    query: str = Field(description="Query text"),
    mode: str = Field(description="Query mode", default="hybrid"),
    top_k: int = Field(description="Number of results", default=10),
) -> dict[str, Any]:
    """Query raw data without LLM."""
    try:
        engine = get_engine(ctx)
        result = await engine.query_data(query=query, mode=mode, top_k=top_k)  # type: ignore
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error in query_data: {e}")
        return format_response(str(e), is_error=True)


# ==================== Memory Management Tools (HGMem) ====================


@mcp.tool(
    name="evolve_memory",
    description="""Trigger HGMem memory evolution based on retrieved context.

Memory evolution:
1. Extracts memory points from context
2. Updates existing memories with new information
3. Creates associations between related concepts
4. Tracks history for temporal reasoning""",
)
async def evolve_memory(
    ctx: Context,
    context: str = Field(description="Context text for memory evolution"),
    query: str = Field(description="Related query to guide evolution"),
) -> dict[str, Any]:
    """Trigger memory evolution."""
    try:
        engine = get_engine(ctx)
        if not engine._memory_evolver:
            return format_response("Memory evolver not initialized", is_error=True)

        result = await engine._memory_evolver.evolve_and_track(
            retrieved_info=context,
            main_query=query,
            subqueries=[],
        )
        return format_response(
            {
                "inserted": len(result.inserted_points),
                "updated": len(result.updated_points),
                "inserted_points": [", ".join(p.involved_objects) for p in result.inserted_points],
                "updated_points": [", ".join(p[1].involved_objects) for p in result.updated_points],
            }
        )
    except Exception as e:
        logger.exception(f"Error evolving memory: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="get_memory_context",
    description="Get current memory context - all memory points formatted for LLM consumption.",
)
async def get_memory_context(
    ctx: Context,
    delimiter: str = Field(description="Delimiter between memory points", default="---"),
) -> dict[str, Any]:
    """Get formatted memory context."""
    try:
        engine = get_engine(ctx)
        if not engine._memory_evolver:
            return format_response({"context": "", "count": 0})

        context = await engine._memory_evolver.get_memory_context()
        points_context = await engine._memory_evolver.get_memory_points_context(delimiter)

        return format_response(
            {
                "context": context,
                "points_context": points_context,
                "memory_points_count": len(engine._memory_evolver.memory_points),
            }
        )
    except Exception as e:
        logger.exception(f"Error getting memory context: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="get_memory_point_info",
    description="Get detailed information about a specific memory point by its identifier.",
)
async def get_memory_point_info(
    ctx: Context,
    identifier: str = Field(description="Memory point identifier"),
) -> dict[str, Any]:
    """Get single memory point info."""
    try:
        engine = get_engine(ctx)
        if not engine._memory_evolver:
            return format_response("Memory evolver not initialized", is_error=True)

        # Convert string identifier back to list for search
        objs = [s.strip() for s in identifier.split(",")]
        info = await engine._memory_evolver.get_memory_point_info(objs)
        return format_response({"info": info})
    except Exception as e:
        logger.exception(f"Error getting memory point info: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="clear_memory",
    description="Clear all memory points. Use with caution - this removes all learned context.",
)
async def clear_memory(ctx: Context) -> dict[str, Any]:
    """Clear all memory points."""
    try:
        engine = get_engine(ctx)
        if not engine._memory_evolver:
            return format_response("Memory evolver not initialized", is_error=True)

        count = len(engine._memory_evolver.memory_points)
        engine._memory_evolver.memory_points.clear()

        return format_response({"cleared": count, "message": f"Cleared {count} memory points"})
    except Exception as e:
        logger.exception(f"Error clearing memory: {e}")
        return format_response(str(e), is_error=True)


# ==================== Knowledge Graph Operations ====================


@mcp.tool(name="create_entity", description="Create a single entity in the Knowledge Graph.")
async def create_entity(
    ctx: Context,
    entity_name: str = Field(description="Name of the entity"),
    entity_type: str = Field(description="Type/category (e.g., PERSON, DRUG, CONCEPT)", default=""),
    description: str = Field(description="Entity description", default=""),
    source_id: str = Field(description="Source document ID", default=""),
) -> dict[str, Any]:
    """Create an entity."""
    try:
        engine = get_engine(ctx)
        result = await engine.create_entity(
            entity_name=entity_name,
            entity_type=entity_type,
            description=description,
            source_id=source_id,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error creating entity: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="create_relation",
    description="Create a relation (edge) between two entities in the Knowledge Graph.",
)
async def create_relation(
    ctx: Context,
    src_entity: str = Field(description="Source entity name"),
    tgt_entity: str = Field(description="Target entity name"),
    description: str = Field(description="Relation description", default=""),
    keywords: str = Field(description="Relation keywords (comma-separated)", default=""),
    source_id: str = Field(description="Source document ID", default=""),
) -> dict[str, Any]:
    """Create a relation between entities."""
    try:
        engine = get_engine(ctx)
        result = await engine.create_relation(
            src_entity=src_entity,
            tgt_entity=tgt_entity,
            description=description,
            keywords=keywords,
            source_id=source_id,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error creating relation: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="get_entity_info",
    description="Get detailed information about an entity including its relations.",
)
async def get_entity_info(
    ctx: Context,
    entity_name: str = Field(description="Entity name to lookup"),
) -> dict[str, Any]:
    """Get entity information."""
    try:
        engine = get_engine(ctx)
        info = await engine.get_entity_info(entity_name)
        if info is None:
            return format_response({"found": False, "entity_name": entity_name})
        return format_response({"found": True, "entity": info})
    except Exception as e:
        logger.exception(f"Error getting entity info: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="get_relation_info",
    description="Get detailed information about a relation between two entities.",
)
async def get_relation_info(
    ctx: Context,
    src_entity: str = Field(description="Source entity name"),
    tgt_entity: str = Field(description="Target entity name"),
) -> dict[str, Any]:
    """Get relation information."""
    try:
        engine = get_engine(ctx)
        info = await engine.get_relation_info(src_entity, tgt_entity)
        if info is None:
            return format_response({"found": False, "src": src_entity, "tgt": tgt_entity})
        return format_response({"found": True, "relation": info})
    except Exception as e:
        logger.exception(f"Error getting relation info: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="get_knowledge_graph",
    description="Get the full Knowledge Graph structure with all entities and relations.",
)
async def get_knowledge_graph(
    ctx: Context,
    node_label: str | None = Field(description="Filter by entity type", default=None),
    max_depth: int = Field(description="Maximum traversal depth", default=3),
) -> dict[str, Any]:
    """Get knowledge graph structure."""
    try:
        engine = get_engine(ctx)
        result = await engine.get_knowledge_graph(
            node_label=node_label,
            max_depth=max_depth,
        )
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error getting knowledge graph: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="delete_entity",
    description="Delete an entity and all its associated relations from the Knowledge Graph.",
)
async def delete_entity(
    ctx: Context,
    entity_name: str = Field(description="Entity name to delete"),
) -> dict[str, Any]:
    """Delete an entity."""
    try:
        engine = get_engine(ctx)
        result = await engine.delete_entity(entity_name)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error deleting entity: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="merge_entities",
    description="Merge two entities - source entity is merged into target, source is deleted.",
)
async def merge_entities(
    ctx: Context,
    source_entity: str = Field(description="Entity to merge from (will be deleted)"),
    target_entity: str = Field(description="Entity to merge into"),
) -> dict[str, Any]:
    """Merge two entities."""
    try:
        engine = get_engine(ctx)
        result = await engine.merge_entities(source_entity, target_entity)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error merging entities: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(name="insert_custom_kg", description="Insert custom entities and relations in bulk.")
async def insert_custom_kg(
    ctx: Context,
    entities: list[dict[str, Any]] = Field(
        description="""List of entity dicts with keys:
        - entity_name (str): Name
        - entity_type (str): Type/category
        - description (str): Description
        - source_id (str): Source document"""
    ),
    relations: list[dict[str, Any]] = Field(
        description="""List of relation dicts with keys:
        - src_id (str): Source entity name
        - tgt_id (str): Target entity name
        - description (str): Relation description
        - keywords (str): Keywords
        - source_id (str): Source document"""
    ),
) -> dict[str, Any]:
    """Insert custom knowledge graph data."""
    try:
        engine = get_engine(ctx)
        result = await engine.insert_custom_kg(entities=entities, relations=relations)
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error inserting custom KG: {e}")
        return format_response(str(e), is_error=True)


# ==================== System Tools ====================


@mcp.tool(
    name="get_health", description="Check the health status of the RAG system and all components."
)
async def get_health(ctx: Context) -> dict[str, Any]:
    """Health check with component status."""
    try:
        engine = get_engine(ctx)
        status = engine.get_status()
        return format_response(
            {
                "status": "healthy" if status["initialized"] else "initializing",
                "version": "0.6.0",
                "components": status["components"],
            }
        )
    except Exception as e:
        return format_response({"status": "unhealthy", "error": str(e)})


@mcp.tool(name="get_graph_stats", description="Get detailed statistics about the Knowledge Graph.")
async def get_graph_stats(ctx: Context) -> dict[str, Any]:
    """Get graph statistics."""
    try:
        engine = get_engine(ctx)
        stats = engine.get_graph_stats()
        return format_response(stats)
    except Exception as e:
        logger.exception(f"Error getting graph stats: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="export_data",
    description="Export all data from the RAG system (entities, relations, chunks).",
)
async def export_data(ctx: Context) -> dict[str, Any]:
    """Export all data."""
    try:
        engine = get_engine(ctx)
        result = await engine.export_data()
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error exporting data: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="clear_cache", description="Clear LLM response cache. Use when you need fresh responses."
)
async def clear_cache(ctx: Context) -> dict[str, Any]:
    """Clear LLM cache."""
    try:
        engine = get_engine(ctx)
        result = await engine.clear_cache()
        return format_response(result)
    except Exception as e:
        logger.exception(f"Error clearing cache: {e}")
        return format_response(str(e), is_error=True)


@mcp.tool(
    name="visualize_graph",
    description="Generate an interactive HTML visualization of the Knowledge Graph.",
)
async def visualize_graph(
    ctx: Context,
    filename: str = Field(description="Output filename", default="graph.html"),
) -> dict[str, Any]:
    """Generate graph visualization."""
    try:
        engine = get_engine(ctx)
        path = await engine.visualize_graph(filename=filename)
        return format_response({"path": str(path), "message": f"Visualization saved to {path}"})
    except Exception as e:
        logger.exception(f"Error generating visualization: {e}")
        return format_response(str(e), is_error=True)


def main() -> None:
    """Entry point for MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
