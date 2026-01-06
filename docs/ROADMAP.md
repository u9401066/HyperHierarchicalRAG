# HyperHierarchicalRAG 整合路線圖

## 🎯 專案定位

**核心目標**：整合 LightRAG (階層式檢索) 與 HGMem (超圖記憶) 兩個強大系統，創建功能完整的 MVP。

**開發策略**：先整合，後創新。

---

## Phase 1: 整合 MVP (目前階段) 🔥

### 1.1 LightRAG 整合 (Hierarchical Retrieval)

**目標**：包裝 LightRAG 的階層式關鍵字抽取與檢索。

```
Infrastructure/Retrieval/
├── HierarchicalRouter.py      # LightRAG Adapter
│   ├── extract_local_keywords()   # 實體級別
│   ├── extract_global_keywords()  # 主題級別
│   └── route_query()              # 根據查詢路由到對應層級
└── __init__.py
```

**交付物**：
- ✅ 安裝 `lightrag-hku` via uv
- 🔲 實作 HierarchicalRouter Adapter
- 🔲 撰寫單元測試確保隔離
- 🔲 文檔：如何使用 Router API

---

### 1.2 HGMem 整合 (Hypergraph Memory)

**目標**：提取 HGMem 核心演算法到 Domain 層。

```
Domain/HypergraphMemory/
├── Entities/
│   ├── HyperNode.py          # 節點實體（對應 data-model.md）
│   ├── HyperEdge.py          # 超邊實體（n-ary relation）
│   └── WorkingMemory.py      # 工作記憶體容器
├── DomainServices/
│   ├── HypergraphBuilder.py  # 構建超圖
│   └── MemoryEvolver.py      # Memory.evolve() 邏輯
└── Repositories/
    └── IHypergraphRepository.py  # DAL 介面定義
```

**交付物**：
- 🔲 研讀 HGMem 論文與 repo 原始碼
- 🔲 實作 HyperNode + HyperEdge 實體
- 🔲 實作 MemoryEvolver (基礎版)
- 🔲 撰寫單元測試
- 🔲 文檔：Hypergraph 核心概念與 API

---

### 1.3 整合層 (Application Layer)

**目標**：結合 Hierarchical Router + Hypergraph Memory。

```
Application/UseCases/
├── QueryProcessor.py         # 統一查詢入口
│   ├── process_query()       # 1. Router 分類
│   │                         # 2. Hypergraph 推理
│   │                         # 3. 返回結果
└── MemoryManager.py          # 記憶體管理
    ├── add_to_memory()       # 新增節點/超邊
    └── evolve_memory()       # 觸發演化
```

**交付物**：
- 🔲 實作 QueryProcessor (整合 Router + Memory)
- 🔲 實作基礎的 MemoryManager
- 🔲 E2E 測試：完整查詢流程
- 🔲 範例腳本：展示整合效果

---

### 1.4 儲存層 (Persistence)

**目標**：實作基礎的 Hypergraph 儲存。

```
Infrastructure/Persistence/
├── Repositories/
│   └── InMemoryHypergraphRepository.py  # 記憶體版本（MVP）
└── DbContext/
    └── (未來擴展：Neo4j, PostgreSQL + pgvector)
```

**交付物**：
- 🔲 實作 InMemoryHypergraphRepository
- 🔲 實作序列化/反序列化 (JSON)
- 🔲 單元測試：CRUD 操作

---

## Phase 2: 創新特性 (整合完成後) 🚀

> **前提**：Phase 1 整合 MVP 完成且穩定運行。

### 2.1 語義分層儲存 (Semantic Tiering)

利用 LightRAG 的 `hl_keywords` 作為超圖「骨架」，`ll_keywords` 作為動態「葉子節點」。

**預期效益**：減少記憶體佔用，提升檢索效率。

---

### 2.2 拓撲剪枝 (Topological Pruning)

引入圖中心性指標（PageRank, Betweenness），對推理路徑進行重要性評分。

**預期效益**：降低推理鏈噪音，提升回答品質。

---

### 2.3 跨模態超邊 (Cross-modal Hyperedges)

將 PDF 中的表格、圖片與文本塊透過同一個超邊連結。

**預期效益**：多模態推理能力（需配合 Asset MCP）。

---

### 2.4 回饋式圖譜進化 (Refinement Loop)

根據查詢結果回饋，自動優化超圖結構。

**預期效益**：自適應學習，長期記憶優化。

---

## 📊 當前進度

| 階段 | 狀態 | 完成度 |
|------|------|--------|
| **Phase 1.0: 環境與架構** | ✅ 完成 | 100% |
| Phase 1.1: LightRAG 整合 | ✅ 完成 | 100% |
| Phase 1.2: HGMem 整合 | ✅ 完成 | 100% |
| Phase 1.3: 整合層 | ✅ 完成 | 100% |
| Phase 1.4: 儲存層 | ✅ 完成 | 100% |
| **Phase 1.5: MCP Server** | ✅ 完成 | 100% |
| **Phase 2: 創新特性** | ⏳ 待開始 | 0% |

---

## 🎯 下一步行動 (Next Actions)

1. **~~安裝依賴~~**：✅ `uv pip install -e ".[dev]"` 完成
2. **~~建立 LightRAG Adapter 骨架~~**：✅ `HierarchicalRouter.py` 完成
3. **~~建立 HGMem Domain 實體~~**：✅ `HyperNode`, `HyperEdge` 完成
4. **~~實作 MemoryEvolver~~**：✅ LLM-driven 記憶演化完成
5. **~~實作 QueryProcessor~~**：✅ 5-step 整合查詢流程完成
6. **~~實作 MCP Server~~**：✅ 11 個 Tools 完成
7. **~~E2E 測試~~**：✅ 13 個測試通過

### 當前優先事項
1. **整合 LightRAG 完整功能**：目前只有 keyword extraction，需要加入 KG retrieval
2. **實作 Neo4j 儲存後端**：取代 InMemory Repository
3. **加入 Embedding 支援**：整合 OpenAI/Local embeddings
4. **撰寫使用文檔**：MCP Server 配置指南

---

## 📚 參考資料

- **整合策略**：[docs/architecture/dependency-strategy.md](docs/architecture/dependency-strategy.md)
- **數據模型**：[docs/architecture/data-model.md](docs/architecture/data-model.md)
- **文獻總結**：[RAG_Literature_Summary.md](RAG_Literature_Summary.md)
- **DDD 規範**：[.github/bylaws/ddd-architecture.md](.github/bylaws/ddd-architecture.md)
