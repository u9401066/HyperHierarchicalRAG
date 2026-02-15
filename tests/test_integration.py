"""
Tests for Infrastructure Adapters and Domain Services Integration

Tests the new integration components:
1. LightRAGKGAdapter
2. VectorStoreAdapter
3. KGMemorySyncService
4. MemoryPointwiseRetriever
5. SQLiteUnifiedRepository
"""

import os
import tempfile

import pytest

from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel
from hyperhierarchical_rag.Domain.services.kg_memory_sync import (
    KGMemorySyncService,
)
from hyperhierarchical_rag.Domain.services.memory_retriever import (
    MemoryPointwiseRetriever,
)

# Import new components
from hyperhierarchical_rag.Infrastructure.adapters.lightrag_kg_adapter import (
    InMemoryKGAdapter,
)
from hyperhierarchical_rag.Infrastructure.adapters.vector_store_adapter import (
    InMemoryVectorStore,
    TextChunksAdapter,
)
from hyperhierarchical_rag.Infrastructure.persistence.sqlite_repository import (
    SQLiteUnifiedRepository,
)

# ============ Test LightRAG KG Adapter ============


class TestInMemoryKGAdapter:
    """Test InMemoryKGAdapter functionality."""

    @pytest.fixture
    def adapter(self):
        return InMemoryKGAdapter()

    @pytest.mark.asyncio
    async def test_upsert_and_get_node(self, adapter):
        """Test basic node operations."""
        await adapter.upsert_node(
            "ENTITY_A",
            {"entity_type": "PERSON", "description": "Test entity A", "source_id": "chunk-001"},
        )

        node = await adapter.get_node("ENTITY_A")
        assert node is not None
        assert node["entity_type"] == "PERSON"
        assert node["description"] == "Test entity A"

    @pytest.mark.asyncio
    async def test_has_node(self, adapter):
        """Test node existence check."""
        assert not await adapter.has_node("UNKNOWN")

        await adapter.upsert_node("TEST", {"description": "test"})
        assert await adapter.has_node("TEST")
        assert await adapter.has_node("test")  # Case insensitive

    @pytest.mark.asyncio
    async def test_upsert_and_get_edge(self, adapter):
        """Test edge operations."""
        await adapter.upsert_node("A", {})
        await adapter.upsert_node("B", {})

        await adapter.upsert_edge(
            "A", "B", {"description": "A relates to B", "keywords": "relation"}
        )

        edge = await adapter.get_edge("A", "B")
        assert edge is not None
        assert edge["description"] == "A relates to B"

    @pytest.mark.asyncio
    async def test_get_neighbor_nodes(self, adapter):
        """Test neighbor retrieval."""
        await adapter.upsert_node("CENTER", {})
        await adapter.upsert_node("NEIGHBOR1", {})
        await adapter.upsert_node("NEIGHBOR2", {})

        await adapter.upsert_edge("CENTER", "NEIGHBOR1", {})
        await adapter.upsert_edge("CENTER", "NEIGHBOR2", {})

        neighbors = await adapter.get_neighbor_nodes("CENTER")
        assert len(neighbors) == 2
        assert "NEIGHBOR1" in neighbors
        assert "NEIGHBOR2" in neighbors

    @pytest.mark.asyncio
    async def test_batch_operations(self, adapter):
        """Test batch node operations."""
        nodes = {
            "NODE1": {"description": "Node 1"},
            "NODE2": {"description": "Node 2"},
            "NODE3": {"description": "Node 3"},
        }

        await adapter.batch_upsert_nodes(nodes)

        results = await adapter.batch_get_nodes(["NODE1", "NODE2", "NODE3"])
        assert len(results) == 3
        assert results["NODE1"]["description"] == "Node 1"


# ============ Test Vector Store Adapter ============


class TestInMemoryVectorStore:
    """Test InMemoryVectorStore functionality."""

    @pytest.fixture
    def store(self):
        return InMemoryVectorStore()

    @pytest.mark.asyncio
    async def test_upsert_and_query(self, store):
        """Test basic vector store operations."""
        await store.upsert(
            {
                "doc1": {"content": "machine learning algorithms"},
                "doc2": {"content": "deep neural networks"},
                "doc3": {"content": "cooking recipes"},
            }
        )

        results = await store.query("machine learning", top_k=2)
        assert len(results) <= 2
        # Should match doc1 better
        assert any("machine" in r.get("content", "").lower() for r in results)

    @pytest.mark.asyncio
    async def test_filter_lambda(self, store):
        """Test filter functionality."""
        await store.upsert(
            {
                "doc1": {"content": "AI research", "type": "paper"},
                "doc2": {"content": "AI news", "type": "article"},
            }
        )

        # Filter only papers
        results = await store.query("AI", filter_lambda=lambda d: d.get("type") == "paper")
        assert all(r.get("type") == "paper" for r in results if "type" in r)


# ============ Test KG Memory Sync Service ============


class TestKGMemorySyncService:
    """Test KGMemorySyncService functionality."""

    @pytest.fixture
    def mock_llm(self):
        async def llm_func(prompt, **kwargs):
            # Return mock response in expected format
            return """
(entity|ENTITY_X|CONCEPT|A test entity){record_delimiter}
(relationship|ENTITY_X|ENTITY_Y|Related|relation_keyword){record_delimiter}
<END>
"""

        return llm_func

    @pytest.fixture
    def sync_service(self, mock_llm):
        kg_adapter = InMemoryKGAdapter()
        entities_vdb = InMemoryVectorStore()
        relationships_vdb = InMemoryVectorStore()

        return KGMemorySyncService(
            kg_adapter=kg_adapter,
            entities_vdb=entities_vdb,
            relationships_vdb=relationships_vdb,
            llm_func=mock_llm,
        )

    @pytest.mark.asyncio
    async def test_collect_absent_entities(self, sync_service):
        """Test collecting absent entities."""
        absent_entities = {
            "ENTITY_X": [["ENTITY_X", "ENTITY_Y"]],
        }

        (
            collected_entities,
            collected_rels,
        ) = await sync_service.collect_absent_entities_relationships(
            absent_entities_hyperedges_kv=absent_entities,
            context_info="Some context about Entity X and Entity Y",
        )

        # Should have created the entity in KG
        assert await sync_service.kg_adapter.has_node("ENTITY_X")


# ============ Test Memory Pointwise Retriever ============


class TestMemoryPointwiseRetriever:
    """Test MemoryPointwiseRetriever functionality."""

    @pytest.fixture
    def retriever(self):
        kg_adapter = InMemoryKGAdapter()
        text_chunks_adapter = TextChunksAdapter(
            kv_storage=None, vector_storage=InMemoryVectorStore()
        )
        return MemoryPointwiseRetriever(
            kg_adapter=kg_adapter, text_chunks_adapter=text_chunks_adapter
        )

    @pytest.mark.asyncio
    async def test_empty_memory_points(self, retriever):
        """Test with no memory points."""
        try:
            result = await retriever.get_memory_pointwise_related_info(
                memory_points=[], query="test query", verbose=False
            )
        except (ConnectionError, OSError):
            pytest.skip("tiktoken requires network access to download encoding")

        assert "Entities" in result
        assert "Sources" in result


# ============ Test SQLite Repository ============


class TestSQLiteUnifiedRepository:
    """Test SQLiteUnifiedRepository functionality."""

    @pytest.fixture
    def repo(self):
        # Use temp file
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        repo = SQLiteUnifiedRepository(db_path=path)
        yield repo
        # Cleanup
        try:
            os.unlink(path)
        except OSError:
            pass

    @pytest.mark.asyncio
    async def test_node_crud(self, repo):
        """Test node CRUD operations."""
        node = HyperNode(
            id="node-1",
            name="Test Node",
            level=NodeLevel.LOCAL,
            description="A test node",
            keywords=["test", "node"],  # List, not Set
        )

        # Create
        await repo.upsert_node(node)

        # Read
        retrieved = await repo.get_node("node-1")
        assert retrieved is not None
        assert retrieved.name == "Test Node"
        assert retrieved.level == NodeLevel.LOCAL

        # Update
        node.description = "Updated description"
        await repo.upsert_node(node)
        updated = await repo.get_node("node-1")
        assert updated.description == "Updated description"

        # Delete
        result = await repo.delete_node("node-1")
        assert result is True
        assert await repo.get_node("node-1") is None

    @pytest.mark.asyncio
    async def test_edge_crud(self, repo):
        """Test edge CRUD operations."""
        # Create nodes first
        await repo.upsert_node(HyperNode(id="a", name="A", level=NodeLevel.LOCAL))
        await repo.upsert_node(HyperNode(id="b", name="B", level=NodeLevel.LOCAL))

        # Create edge - use correct HyperEdge attributes
        edge = HyperEdge(
            id="edge-1",
            node_ids={"a", "b"},  # Set
            relation="A to B",  # Not description
            context="Edge context",
        )
        await repo.upsert_edge(edge)

        # Read
        retrieved = await repo.get_edge("edge-1")
        assert retrieved is not None
        assert "a" in retrieved.node_ids

        # Get edges for node
        edges = await repo.get_edges_for_node("a")
        assert len(edges) == 1

        # Delete
        await repo.delete_edge("edge-1")
        assert await repo.get_edge("edge-1") is None

    @pytest.mark.asyncio
    async def test_find_by_keywords(self, repo):
        """Test keyword search."""
        await repo.upsert_node(
            HyperNode(
                id="node-ml",
                name="ML Node",
                level=NodeLevel.LOCAL,
                keywords=["machine", "learning", "ai"],  # List, not Set
            )
        )
        await repo.upsert_node(
            HyperNode(
                id="node-web",
                name="Web Node",
                level=NodeLevel.GLOBAL,
                keywords=["web", "api", "rest"],  # List, not Set
            )
        )

        # Search
        results = await repo.find_by_keywords(["machine", "learning"])
        assert len(results) == 1
        assert results[0].id == "node-ml"

        # Search with level filter
        results = await repo.find_by_keywords(["web"], level=NodeLevel.GLOBAL)
        assert len(results) == 1
        assert results[0].level == NodeLevel.GLOBAL

    @pytest.mark.asyncio
    async def test_find_connected_nodes(self, repo):
        """Test multi-hop traversal."""
        # Create chain: A - B - C - D
        for name in ["A", "B", "C", "D"]:
            await repo.upsert_node(HyperNode(id=name.lower(), name=name, level=NodeLevel.LOCAL))

        await repo.upsert_edge(HyperEdge(id="ab", node_ids={"a", "b"}))  # Set
        await repo.upsert_edge(HyperEdge(id="bc", node_ids={"b", "c"}))  # Set
        await repo.upsert_edge(HyperEdge(id="cd", node_ids={"c", "d"}))  # Set

        # 1 hop from A should get B
        results_1 = await repo.find_connected_nodes("a", max_hops=1)
        assert len(results_1) == 1
        assert results_1[0].id == "b"

        # 2 hops should get B, C
        results_2 = await repo.find_connected_nodes("a", max_hops=2)
        assert len(results_2) == 2

        # 3 hops should get B, C, D
        results_3 = await repo.find_connected_nodes("a", max_hops=3)
        assert len(results_3) == 3

    @pytest.mark.asyncio
    async def test_stats(self, repo):
        """Test statistics."""
        await repo.upsert_node(HyperNode(id="1", name="1", level=NodeLevel.LOCAL))
        await repo.upsert_node(HyperNode(id="2", name="2", level=NodeLevel.GLOBAL))
        await repo.upsert_edge(HyperEdge(id="e1", node_ids={"1", "2"}))  # Set

        stats = await repo.get_stats()
        # get_stats returns flat counts: {"nodes": int, "edges": int, ...}
        assert stats["nodes"] == 2
        assert stats["edges"] == 1


# ============ Run Tests ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
