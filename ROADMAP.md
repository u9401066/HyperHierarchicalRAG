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
│   │ • Ollama/OpenAI │      │ • Reorganize    │                     │
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
│              │  (22+ Tools)    │                                    │
│              └─────────────────┘                                    │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## ✅ Phase 1: 基礎架構 (已完成)

### v0.1.0 - 專案初始化 (2025-01)
- [x] DDD 架構建立 (Domain/Application/Infrastructure)
- [x] Memory Bank 系統
- [x] Claude Skills 基礎架構
- [x] Git 文檔自動更新

### v0.2.0 - 核心元件 (2025-01)
- [x] `HyperNode` / `HyperEdge` 實體定義
- [x] `MemoryEvolver` 基礎版本 (`evolve()`)
- [x] `QueryProcessor` 框架
- [x] `RAGEngine` 統一入口
- [x] 視覺化模組 (`HypergraphVisualizer`, `QueryPathVisualizer`)

### v0.3.0 - HGMem 功能移植 (2025-01-06)
- [x] `EnhancedMemoryEvolver` 完整版本
  - [x] `evolve_and_track()` - 演化 + 追蹤歷史
  - [x] `reorganize_memory()` - 記憶重組/合併
  - [x] `get_extended_info()` - 鄰居擴展上下文
  - [x] `clear_memory()` - 清除記憶
- [x] Ollama 整合 (使用 LightRAG 內建支援)
- [x] 移除冗餘依賴 (`faiss-cpu`, `sentence-transformers`)
- [x] 13 個 E2E 測試通過

---

## 🚧 Phase 2: 深度整合 (進行中)

### v0.4.0 - LightRAG ↔ Hypergraph 整合 (目標: 2025-01)
- [ ] **KG Adapter 實現**
  - [ ] `LightRAGKGAdapter` 類 - 連接 LightRAG 的 Knowledge Graph
  - [ ] `get_neighbors()` - 從 KG 獲取鄰居節點
  - [ ] `upsert_entity()` - 同步實體到 KG
- [ ] **雙向數據同步**
  - [ ] `collect_absent_entities_relationships()` - 補全缺失實體
  - [ ] 自動將新 MemoryPoint 同步到 LightRAG KG
- [ ] **Repository 實現**
  - [ ] `HypergraphRepository` (Infrastructure 層)
  - [ ] 支援 Neo4j / Milvus 持久化

### v0.5.0 - 進階查詢 (目標: 2025-02)
- [ ] **完整查詢流程移植**
  - [ ] `hgmem_query()` - HGMem 原始查詢模式
  - [ ] `get_memory_pointwise_related_info()` - 記憶點相關檢索
- [ ] **向量庫整合**
  - [ ] `entities_vdb` - 實體向量索引
  - [ ] `relationships_vdb` - 關係向量索引
  - [ ] `text_chunks_vdb` - 文本塊向量索引
- [ ] **查詢模式擴展** (參考 GraphRAG)
  - [ ] Local Search (實體級)
  - [ ] Global Search (社群級, Map-Reduce)
  - [ ] DRIFT Search (迭代式探索)

---

## 📋 Phase 3: MCP 工具化 (計劃中)

### v0.6.0 - MCP Server 完整實現 (目標: 2025-02)
參考: `desimpkins/daniel-lightrag-mcp` 的 22 工具設計

#### Document Tools (8)
- [ ] `insert_text` - 插入文本
- [ ] `insert_texts` - 批量插入
- [ ] `upload_document` - 上傳文件
- [ ] `scan_documents` - 掃描新文件
- [ ] `get_documents` - 列出文件
- [ ] `get_documents_paginated` - 分頁列出
- [ ] `delete_document` - 刪除文件
- [ ] `clear_documents` - 清空所有

#### Query Tools (4)
- [ ] `query_text` - 基本查詢 (naive/local/global/hybrid)
- [ ] `query_text_stream` - 串流查詢
- [ ] `query_with_memory` - 帶記憶查詢 (HGMem 特色)
- [ ] `query_and_evolve` - 查詢 + 演化記憶

#### Knowledge Graph Tools (7)
- [ ] `get_knowledge_graph` - 獲取 KG 結構
- [ ] `get_graph_labels` - 獲取標籤
- [ ] `check_entity_exists` - 檢查實體
- [ ] `update_entity` - 更新實體
- [ ] `update_relation` - 更新關係
- [ ] `delete_entity` - 刪除實體
- [ ] `delete_relation` - 刪除關係

#### Hypergraph Tools (新增, HGMem 特色)
- [ ] `get_memory_points` - 獲取記憶點
- [ ] `evolve_memory` - 手動演化
- [ ] `reorganize_memory` - 重組記憶
- [ ] `get_extended_info` - 擴展上下文
- [ ] `traverse_hyperedges` - 超邊遍歷

#### System Tools (5)
- [ ] `get_health` - 健康檢查
- [ ] `get_pipeline_status` - 管道狀態
- [ ] `get_document_status_counts` - 文件統計
- [ ] `clear_cache` - 清除緩存
- [ ] `get_track_status` - 追蹤狀態

---

## 🔮 Phase 4: 平台化 (長期目標)

### v1.0.0 - 生產就緒 (目標: 2025-Q2)
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
| QueryProcessor | ⚠️ 框架 | 60% |
| RAGEngine | ⚠️ 框架 | 60% |
| LightRAG Adapter | ❌ 未開始 | 0% |
| Hypergraph Repository | ❌ 未開始 | 0% |
| MCP Server | ⚠️ 基礎 | 20% |
| 視覺化 | ✅ 完成 | 100% |
| **總體整合度** | **🟡** | **~55%** |

---

## 參考資源

### 核心依賴
- [LightRAG](https://github.com/HKUDS/LightRAG) - 階層式 RAG
- [HGMem](https://github.com/HKUDS/HGMem) - 超圖記憶

### 參考實現
- [daniel-lightrag-mcp](https://github.com/desimpkins/daniel-lightrag-mcp) - MCP 工具設計
- [Yuxi-Know](https://github.com/xerrors/Yuxi-Know) - 平台架構
- [GraphRAG](https://github.com/microsoft/graphrag) - 查詢引擎設計
