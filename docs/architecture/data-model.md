# HyperHierarchicalRAG Data Model Design

## 0. 設計決策：單層 Hypergraph + 節點 Level 屬性

### 問題：High/Low Level 與 Hypergraph 如何整合？

**選項分析：**

| 方案 | 描述 | 優點 | 缺點 |
|------|------|------|------|
| A. 雙層分離 | Local Graph + Global Graph | 清晰分離 | 跨層查詢困難 |
| B. 疊層 Graph | 兩個獨立 Hypergraph | 各自優化 | 資料重複、同步困難 |
| **C. 單層統一** | 單一 Hypergraph + Level 屬性 | 簡潔、允許跨層推理 | 需要 Level 過濾 |

**採用方案 C：單層 Hypergraph + 節點 Level 屬性**

```
                    ╔══════════════════════════════════════╗
                    ║       Unified Hypergraph             ║
                    ╠══════════════════════════════════════╣
                    ║                                      ║
                    ║  [GLOBAL] Sedation    [GLOBAL] Anesthesia
                    ║       │                    │         ║
                    ║       └────────┬───────────┘         ║
                    ║                │                     ║
                    ║     ╔══════════╧══════════╗          ║
                    ║     ║   HyperEdge (n=5)   ║          ║
                    ║     ║ "ICU sedation drugs"║          ║
                    ║     ╚══════════╤══════════╝          ║
                    ║          ┌─────┼─────┐               ║
                    ║          │     │     │               ║
                    ║  [LOCAL] │ [LOCAL]  [LOCAL]          ║
                    ║  Propofol Remimazolam Delirium       ║
                    ║                                      ║
                    ╚══════════════════════════════════════╝

關鍵設計：
1. 節點有 level 屬性 (LOCAL/GLOBAL)
2. Hyperedge 可以跨 level 連接
3. 查詢時根據 keyword 類型選擇起始節點
4. Hyperedge 實現 n-ary 關係（傳統 KG 做不到）
```

**為何不用雙層 Graph？**

- LightRAG 的 High/Low 是**查詢路由**概念，不是**儲存結構**
- Hyperedge 的價值在於連接**任意數量**的節點
- 跨層連結是常見場景（主題 → 具體實體）

---

## 1. 核心實體 (Core Entities)

### 1.1 Node (實體節點)

支援 LightRAG 的階層式標籤特性。

| 欄位名 | 類型 | 說明 |
| :--- | :--- | :--- |
| `id` | UUID/String | 節點唯一識別碼 (通常為實體名稱的 Hash) |
| `name` | String | 實體名稱 |
| `description` | Text | 實體描述與上下文 |
| `level` | Enum | 階層級別: `LOCAL` (具體實體), `GLOBAL` (抽象概念/主題) |
| `keywords` | List\<String\> | 用於倒排索引的關鍵字 |
| `embedding` | Vector | 語義嵌入向量 |

### 1.2 HyperEdge (超邊)

支援 HGMem 的多元關係建模與記憶演化。

| 欄位名 | 類型 | 說明 |
| :--- | :--- | :--- |
| `id` | UUID/String | 超邊唯一識別碼 |
| `nodes` | List\<NodeID\> | 成員節點列表 (n-ary)，**可跨 Level** |
| `relation` | String | 關係類型描述 |
| `weight` | Float | 關係強度或重要性 |
| `context` | Text | 該關係發生的具體文本背景 |
| `evolve_count` | Int | 記憶演化次數 (演化式 RAG 核心) |

## 2. 整合機制 (Integration Logic)

1. **Semantic Tiering**: 將 LightRAG 的 `hl_keywords` 映射為 `GLOBAL` 級別的 Node，`ll_keywords` 映射為 `LOCAL` 級別。
2. **Topological Memory**: 當系統進行檢索時，利用 HyperEdge 進行「跳躍式推理」，越過傳統 Graph 的二元限制。
3. **Cross-Level Hyperedges**: 允許 HyperEdge 同時連結 `LOCAL` 與 `GLOBAL` 節點，實現從細節到大局的快速轉換。

## 3. 查詢流程 (Query Flow)

```
User Query: "Compare propofol and remimazolam for ICU sedation"
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: LightRAG Keyword Extraction                             │
│ ─────────────────────────────────────                            │
│ ll_keywords: ["propofol", "remimazolam", "ICU"]                 │
│ hl_keywords: ["comparison", "sedation"]                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Node Retrieval by Level                                 │
│ ─────────────────────────────────                                │
│ LOCAL nodes:  Propofol, Remimazolam, ICU (from ll_keywords)     │
│ GLOBAL nodes: Comparison, Sedation (from hl_keywords)            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Hyperedge Traversal (KEY INTEGRATION!)                  │
│ ─────────────────────────────────────────────                    │
│                                                                  │
│ Starting from: {Propofol, Remimazolam, Sedation}                │
│                                                                  │
│ Found Hyperedge: {Propofol, Remimazolam, Delirium, ICU, Sedation}│
│ Description: "Both drugs used for ICU sedation, differ in       │
│              delirium incidence"                                │
│                                                                  │
│ → Discovered: Delirium (not in original query!)                 │
│ → This is what LightRAG alone cannot find!                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Memory Evolution                                        │
│ ─────────────────────────                                        │
│ LLM analyzes context → Creates/updates memory points            │
│ New Hyperedge stored for future queries                         │
└─────────────────────────────────────────────────────────────────┘
```
