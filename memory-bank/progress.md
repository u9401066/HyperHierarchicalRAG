# Progress (Updated: 2026-01-07)

## Done

- Fix LightRAG LLM integration (hashing_kv issue)
- Implement Hypergraph multi-hop expansion (BFS)
- Implement SQLite persistence for Memory Points
- Create unified RAGEngine query flow with hypergraph step
- Update MCP server with 22 tools
- Initial testing of long RAG chain via MCP queries
- Document Dual-Path Storage Strategy (SQLite vs Enterprise) in README/ROADMAP

## Doing



## Next

- Implement SQLiteUnifiedRepository (KG + Chunks + Memory integration)
- Refactor RAGEngine to support STORAGE_TYPE switching
- Add basic reranker for multi-hop expanded entities
- Create Docker Compose for Enterprise Stack (Milvus/PG)
