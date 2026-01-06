# Active Context

## Current Status
- 🎯 **核心策略**：先整合，後創新 (整合 MVP 優先)
- ✅ **Phase 1 核心整合基本完成**
- 🔄 進入 MCP Server 實作階段

## Architecture Decision Log

### 關鍵決策：單層 Hypergraph + 節點 Level 屬性
- **問題**: LightRAG 的 High/Low Level 如何與 HGMem 的 Hypergraph 整合？
- **選項**: A) 雙層分離 Graph, B) 疊層獨立 Graph, C) 單層統一 + Level 屬性
- **決策**: **採用方案 C**
- **原因**: 
  1. LightRAG 的 High/Low 是查詢路由概念，不是儲存結構
  2. Hyperedge 的價值在於跨 Level 連接（主題↔實體）
  3. 單層結構簡潔，查詢時用 Level 過濾即可

## Implemented Components

### Domain Layer
- `HyperNode`: 節點實體 (id, name, level, keywords, embedding)
- `HyperEdge`: 超邊實體 (n-ary node_ids, evolve_count, evolve() method)
- `NodeLevel`: Enum (LOCAL, GLOBAL)
- `MemoryEvolver`: LLM-driven 記憶演化服務 (EVOLVE_MEMORY_*_PROMPT)
- `IHypergraphRepository`: Repository 介面

### Infrastructure Layer
- `InMemoryHypergraphRepository`: MVP 記憶體儲存 + keyword index + BFS
- `HierarchicalRouter`: LightRAG Adapter (keyword extraction)

### Application Layer
- `QueryProcessor`: 5-step 整合查詢流程
  1. Keyword Extraction (LightRAG)
  2. KG Retrieval (LightRAG)
  3. Hyperedge Traversal (HGMem topology)
  4. Memory Evolution (HGMem evolve)
  5. Response Generation

## Next Steps
- 完成 MCP Server Tools 實作
- 實作 LightRAG 完整 wrapper (目前只有 keyword extraction)
- End-to-end 測試
- 補充文檔與 README 更新
