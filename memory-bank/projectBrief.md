# Project Brief

## 🎯 專案目的

開發一個結合 **超圖 (Hypergraph)** 與 **階層式檢索 (Hierarchical Retrieval)** 的新型 RAG 系統 (**HyperHierarchicalRAG**)。

**開發策略**：**先整合，後創新** — 優先完成 LightRAG 與 HGMem 的功能整合，創新特性作為 Phase 2 擴展。

### 核心問題
1. **複雜關係建模**：如何解決傳統 KG RAG 僅能處理二元關係的侷限？ (整合 HGMem Hypergraph)
2. **全局與局部平衡**：如何在處理海量知識時兼顧局部細節與全局主題？ (整合 LightRAG Hierarchical Retrieval)
3. **推理連貫性**：如何在多步推理中保持上下文的連貫性？ (整合 HGMem Working Memory)

### MVP 目標 (Phase 1)
- 包裝 LightRAG 的階層式關鍵字抽取與路由
- 提取 HGMem 的超圖記憶演化核心邏輯
- 實作整合層 API (QueryProcessor + MemoryManager)
- 基礎儲存層 (InMemory Repository)

### 創新特性 (Phase 2 - 整合穩定後)
- 語義分層儲存 (Semantic Tiering)
- 拓撲剪枝 (Topological Pruning)
- 跨模態超邊 (Cross-modal Hyperedges)
- 回饋式圖譜進化 (Refinement Loop)
