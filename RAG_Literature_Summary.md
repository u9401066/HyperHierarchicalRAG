# RAG 文獻總結：Hypergraph 與 Hierarchical 檢索技術

## 1. HGMem (doc_2512_23959v2_2526f6)
- **核心技術**：基於超圖（Hypergraph）的工作記憶體。
- **創新點**：使用超邊（Hyperedges）捕捉高階相關性（n-ary relations），解決傳統圖形僅能捕捉二元關係的問題。
- **機制**：
  - `Memory.evolve()`: 隨著檢索過程更新超圖。
  - `Evolve-Explain-Finalize`: 多步推理策略。
- **侷限**：未強調高低維度概念的階層式檢索。

## 2. LightRAG
- **核心技術**：基於知識圖譜（Knowledge Graph）的雙層檢索。
- **創新點**：`Local`（低階實體）與 `Global`（高階主題）關鍵字檢索。
- **機制**：
  - `ll_keywords`: 實體級別檢索。
  - `hl_keywords`: 摘要與模式級別檢索。
- **侷限**：底層使用二元邊圖形，難以處理複雜的多向關聯。

## 3. TREX (Microsoft)
- **核心技術**：Graph-based + Vector-based Hybrid RAG。
- **創新點**：成本效益高的檢索演算法，比傳統 Graph RAG 更快速。
- **機制**：結合圖結構深度與向量檢索的廣度。

## 4. PKG (Pseudo-Knowledge Graph)
- **核心技術**：Meta-Path Guided Retrieval。
- **創新點**：不依賴靜態圖譜，而是動態引導檢索路徑。

## 5. URAG (Unified Hybrid RAG)
- **核心技術**：統一混合檢索。
- **創新點**：整合多種檢索模式以適應不同問題類型。

## 6. FWHDNN (arXiv:2501.14399)
- **核心技術**：Wavelet Hypergraph Diffusion。
- **創新點**：多層級簇狀編碼（Multi-level cluster-wise encoding）。
- **應用**：主要用於推薦系統，但其多尺度拓撲關係捕捉技術與 RAG 具相關性。

## 7. 整合缺口與未來研究方向 (Filling the Gaps)

### A. 語義分層儲存 (Semantic Tiering)
- **缺口**：HGMem 的工作記憶體受限於上下文長度，而 LightRAG 的全局圖譜過於龐大。
- **對策**：利用 LightRAG 的 `hl_keywords` 作為超圖的「骨架」，將 `ll_keywords` 相關的細節實體作為動態置換的「葉子節點」，實現分層式的內存管理。

### B. 拓撲剪枝與信號強化 (Topological Pruning)
- **缺口**：超圖推理鏈過長時會產生噪音。
- **對策**：引入 FWHDNN 中的小波擴散或圖中心性指標，對推理路徑進行重要性評分，自動剪除無效的超邊。

### C. 跨模態超邊連結 (Cross-modal Hyperedges)
- **缺口**：現有系統多專注於純文本，忽視了圖表與文字的深度關聯。
- **對策**：將 PDF 中的表格 (`table`)、圖片 (`figure`) 與文本塊 (`chunk`) 透過同一個超邊連結。在「長 RAG 鏈」推理時，系統能同時參考圖表數據與描述文字。

### D. 回饋式圖譜進化 (Refinement Loop)
- **缺口**：索引階段後的圖譜通常是靜態的。
- **對策**：將成功的推理路徑（Winning Chains）寫回長期知識圖譜中，強化這些高頻路徑的權重，實現「越用越聰明」的功能。
