# HyperHierarchicalRAG - Roadmap

專案發展路線圖：整合 LightRAG + HGMem 的進階 RAG 系統。

---

## 🎯 專案願景

**HyperHierarchicalRAG** = LightRAG (階層式檢索) + HGMem (超圖記憶) + MCP (工具整合)

```
┌────────────────────────────────────────────────────────────────────┐
│                    HyperHierarchicalRAG Architecture                │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────┐      ┌─────────────────┐                     │
│   │    LightRAG     │◄────►│     HGMem       │                     │
│   │ (Hierarchical)  │      │  (Hypergraph)   │                     │
│   │                 │      │                 │                     │
│   │ • Local/Global  │      │ • N-ary edges   │                     │
│   │ • KG retrieval  │      │ • Memory evolve │                     │
│   │ • Ollama/OpenAI │      │ • Chain expand  │                     │
│   └────────┬────────┘      └────────┬────────┘                     │
│            │                        │                               │
│            └──────────┬─────────────┘                               │
│                       │                                             │
│              ┌────────▼────────┐                                    │
│              │   RAGEngine     │                                    │
│              │  (Unified API)  │                                    │
│              └────────┬────────┘                                    │
│                       │                                             │
│              ┌────────▼────────┐                                    │
│              │   MCP Server    │                                    │
│              │  (22 Tools)     │                                    │
│              └─────────────────┘                                    │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## ✅ Phase 1: 基礎架構 (已完成)

### v0.1.0 - 專案初始化 (2025-12)

- [x] DDD 架構建立 (Domain/Application/Infrastructure)
- [x] Memory Bank 系統
- [x] Claude Skills 基礎架構
- [x] Git 文檔自動更新

### v0.2.0 - 核心元件 (2025-12)

- [x] `HyperNode` / `HyperEdge` 實體定義
- [x] `MemoryEvolver` 基礎版本 (`evolve()`)
- [x] `QueryProcessor` 框架
- [x] `RAGEngine` 統一入口
- [x] 視覺化模組 (`HypergraphVisualizer`, `QueryPathVisualizer`)

### v0.3.0 - HGMem 功能移植 (2025-12)

- [x] `EnhancedMemoryEvolver` 完整版本
  - [x] `evolve_and_track()` - 演化 + 追蹤歷史
  - [x] `reorganize_memory()` - 記憶重組/合併
  - [x] `get_extended_info()` - 鄰居擴展上下文
  - [x] `clear_memory()` - 清除記憶
- [x] Ollama 整合 (使用 LightRAG 內建支援)
- [x] 移除冗餘依賴 (`faiss-cpu`, `sentence-transformers`)
- [x] 13 個 E2E 測試通過

### v0.4.0 - 整合 Adapters (2026-01-05)

- [x] `LightRAGKGAdapter` - 連接 LightRAG Knowledge Graph
- [x] `VectorStoreAdapter` - 向量庫統一介面
- [x] `TextChunksAdapter` - KV + Vector 組合存儲
- [x] `KGMemorySyncService` - collect_absent_entities_relationships()
- [x] `MemoryPointwiseRetriever` - get_memory_pointwise_related_info()
- [x] `SQLiteHypergraphRepository` - 超圖持久化存儲
- [x] InMemory adapters 用於測試
- [x] 27 個測試通過 (13 E2E + 14 整合)

### v0.5.0 - RAGEngine 整合 (2026-01-06)

- [x] **Adapters 自動初始化**
  - [x] RAGEngine 啟動時自動創建 KG/Vector Adapters
  - [x] 從 LightRAG 實例提取 entities_vdb, relationships_vdb, chunks_vdb
  - [x] 初始化 KGMemorySyncService 和 MemoryPointwiseRetriever
- [x] **完整查詢流程**
  - [x] 查詢 → 記憶演化 → 缺失實體補全 → 結果返回
  - [x] 支援 local/global/hybrid 三種模式
- [x] **配置簡化**
  - [x] 單人模式預設配置 (JSON + NanoVectorDB + NetworkX)
  - [x] 環境變數覆蓋

### v0.6.0 - MCP Server 完整版 (2026-01-07) ✅ CURRENT

- [x] **MCP Server 22 Tools**
  - [x] Document Tools: `insert_document`, `insert_text`, `insert_batch`
  - [x] Query Tools: `query`, `query_simple`, `query_data`, `export_data`
  - [x] Memory Tools: `evolve_memory`, `get_memory_context`, `clear_memory_points`
  - [x] Graph Tools: `get_entity_info`, `get_relation_info`, `get_knowledge_graph`, `get_graph_stats`
  - [x] KG Management: `insert_custom_kg`, `delete_document`, `delete_entity`
  - [x] System Tools: `get_health`, `clear_cache`
- [x] **Hypergraph Chain Expansion** 🎉
  - [x] `_expand_via_hypergraph()` - 長 RAG 鏈多跳推理
  - [x] 2-hop BFS traversal 透過 Memory Points 發現間接實體
  - [x] `_extract_seed_entities()` 種子實體提取
- [x] **Memory Points 持久化**
  - [x] SQLite 存儲 (`memory_points`, `subquery_history` 表)
  - [x] 啟動時自動載入
  - [x] 查詢後自動保存

---

## 🚧 Phase 2: 功能完善 (進行中)

### v0.7.0 - 進階功能 (目標: 2026-01)

- [ ] **進階查詢**
  - [ ] `hgmem_query()` - HGMem 原始查詢模式
  - [ ] DRIFT Search (迭代式探索)
- [ ] **記憶管理 UI**
  - [ ] `reorganize_memory` - 記憶重組 Tool
  - [ ] 記憶歷史查看
  - [ ] 記憶匯出/匯入
- [ ] **效能優化**
  - [ ] LRU Cache for frequently accessed entities
  - [ ] Batch processing optimization
- [ ] **文檔**
  - [ ] 完整 API 文檔
  - [ ] 使用範例
  - [ ] 部署指南

### v0.8.0 - 多人模式支援 (目標: 2026-Q1)

> 參考文檔: `docs/MCP_MULTIUSER_ARCHITECTURE.md`

- [ ] **存儲後端自動偵測**
  - [ ] PostgreSQL 全家桶 (PGKVStorage + PGVectorStorage + PGGraphStorage)
  - [ ] MongoDB 全家桶
  - [ ] 混合架構 (Redis + Milvus + Neo4j)
- [ ] **內部 LLM 配置**
  - [ ] MCP 模式下的自動實體補全
  - [ ] 小模型 (qwen2:7b) 處理自動化任務
- [ ] **Session 管理**
  - [ ] 多用戶 Session 隔離
  - [ ] Session 超時管理
- [ ] **SQLite WAL 增強**
  - [ ] 輕量級多人支援
  - [ ] 讀寫分離

---

## 🔮 Phase 3: 平台化 (長期目標)

### v1.0.0 - 生產就緒 (目標: 2026-Q2)

參考: `xerrors/Yuxi-Know` 平台架構

- [ ] **Web UI**
  - [ ] Vue.js 3 + Ant Design Vue
  - [ ] 知識庫管理介面
  - [ ] 查詢視覺化
  - [ ] 記憶演化追蹤

- [ ] **RAG 評估系統**
  - [ ] Benchmark 上傳/生成
  - [ ] 評估指標計算 (Recall/F1/LLM Judge)
  - [ ] 結果視覺化

- [ ] **多租戶支援**
  - [ ] 知識庫隔離
  - [ ] 用戶權限管理

---

## 📊 整合狀態摘要

| 組件 | 狀態 | 完成度 |
|------|------|--------|
| DDD 架構 | ✅ 完成 | 100% |
| HyperNode/HyperEdge | ✅ 完成 | 100% |
| MemoryEvolver (基礎) | ✅ 完成 | 100% |
| EnhancedMemoryEvolver | ✅ 完成 | 100% |
| LightRAGKGAdapter | ✅ 完成 | 100% |
| VectorStoreAdapter | ✅ 完成 | 100% |
| KGMemorySyncService | ✅ 完成 | 100% |
| MemoryPointwiseRetriever | ✅ 完成 | 100% |
| SQLiteHypergraphRepository | ✅ 完成 | 100% |
| **Hypergraph Chain Expansion** | ✅ 完成 | 100% |
| **Memory Points Persistence** | ✅ 完成 | 100% |
| QueryProcessor | ✅ 完成 | 100% |
| RAGEngine | ✅ 完成 | 100% |
| **MCP Server (22 Tools)** | ✅ 完成 | 100% |
| 視覺化 | ✅ 完成 | 100% |
| **總體整合度** | **🟢** | **~95%** |

---

## 參考資源

### 核心依賴

- [LightRAG](https://github.com/HKUDS/LightRAG) - 階層式 RAG
- [HGMem](https://github.com/HKUDS/HGMem) - 超圖記憶

### 參考實現

- [daniel-lightrag-mcp](https://github.com/desimpkins/daniel-lightrag-mcp) - MCP 工具設計
- [Yuxi-Know](https://github.com/xerrors/Yuxi-Know) - 平台架構
- [GraphRAG](https://github.com/microsoft/graphrag) - 查詢引擎設計
