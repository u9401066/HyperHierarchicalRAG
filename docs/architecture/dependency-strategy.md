# 依賴整合策略 (Dependency Integration Strategy)

## 架構決策記錄 (ADR)

### 決策：如何整合 LightRAG 與 HGMem

**日期**：2026-01-06  
**狀態**：已採納

---

## 背景 (Context)

我們需要整合兩個現有系統：

1. **LightRAG**：
   - ✅ 有 PyPI 套件 (`lightrag-hku`)
   - 📦 龐大完整的實作
   - 🎯 我們需要：Hierarchical Router (Local/Global Keywords)

2. **HGMem**：
   - ❌ 無 PyPI 套件
   - 📂 僅有 GitHub repository
   - 🎯 我們需要：Hypergraph Memory + Memory.evolve()

---

## 決策 (Decision)

### 策略 A：LightRAG (PyPI 依賴)

**做法**：透過 `uv` 安裝完整套件，但僅引用核心模組。

```toml
[project]
dependencies = [
    "lightrag-hku>=0.1.0",
]
```

**在我們的程式碼中**：
```python
# src/Infrastructure/Retrieval/HierarchicalRouter.py
from lightrag.kg.keyword_extractor import extract_keywords  # 假設的 API

class HierarchicalRouter:
    """包裝 LightRAG 的階層式檢索邏輯"""
    
    def extract_local_keywords(self, text: str) -> List[str]:
        # 使用 LightRAG 的實體抽取
        return extract_keywords(text, level="local")
    
    def extract_global_keywords(self, text: str) -> List[str]:
        # 使用 LightRAG 的主題抽取
        return extract_keywords(text, level="global")
```

**優點**：
- ✅ 快速整合，不需要重新實作關鍵字抽取邏輯
- ✅ 自動獲得上游更新（bug fixes, improvements）

**缺點**：
- ⚠️ 依賴整個套件（可能有不需要的部分）
- ⚠️ 受限於 LightRAG 的 API 設計

---

### 策略 B：HGMem (核心邏輯整合)

**做法**：將 HGMem 的核心演算法提取到我們的 Domain 層。

```
src/Domain/HypergraphMemory/
├── Entities/
│   ├── HyperNode.py          # 對應 data-model.md 的 Node
│   ├── HyperEdge.py          # 對應 data-model.md 的 HyperEdge
│   └── WorkingMemory.py      # 工作記憶體容器
├── DomainServices/
│   ├── MemoryEvolver.py      # 實作 Memory.evolve() 邏輯
│   └── HypergraphBuilder.py  # 構建超圖結構
└── Repositories/
    └── IHypergraphRepository.py  # DAL 介面
```

**實作方式**：
1. 閱讀 HGMem 論文與 repo 原始碼
2. 提取核心演算法（超邊構建、記憶演化、推理鏈）
3. 重新實作為符合 DDD 的 Domain 邏輯
4. 在 `decisionLog.md` 記錄演算法來源與改動

**優點**：
- ✅ 完全掌控實作細節
- ✅ 符合 DDD 架構（Domain 不依賴外部套件）
- ✅ 可針對我們的需求優化

**缺點**：
- ⚠️ 需要時間理解與重新實作
- ⚠️ 需要自行維護更新

---

## 替代方案 C：Git Submodule (不推薦)

```bash
git submodule add https://github.com/original/hgmem.git external/hgmem
```

**為何不推薦**：
- ❌ 違反 DDD 原則（Domain 應該獨立於外部 repo）
- ❌ 子模組管理複雜
- ❌ 難以針對需求進行客製化

---

## 最終建議 (Recommendation)

### 🎯 採用混合策略

| 元件 | 策略 | 理由 |
|------|------|------|
| **Hierarchical Router** | PyPI 依賴 (LightRAG) | 階層式關鍵字抽取是成熟功能，不需重新發明輪子 |
| **Hypergraph Memory** | 核心邏輯整合 | 超圖演化是我們的核心創新點，需要完全掌控 |

### 📋 實作步驟

1. **Phase 1: 環境建立**
   ```bash
   uv venv
   uv pip install -e ".[dev]"
   ```

2. **Phase 2: LightRAG 整合**
   - 在 `Infrastructure/Retrieval/` 建立 Adapter
   - 包裝 LightRAG 的關鍵字抽取 API
   - 撰寫單元測試確保隔離

3. **Phase 3: HGMem 核心邏輯**
   - 在 `Domain/HypergraphMemory/` 實作核心演算法
   - 參考 HGMem 論文 Appendix 的虛擬碼
   - 記錄設計決策到 `memory-bank/architect.md`

4. **Phase 4: 整合層**
   - 在 `Application/UseCases/` 建立高層 API
   - 結合 Hierarchical Router + Hypergraph Memory

---

## 合規性檢查 (Compliance)

✅ 符合憲法第 4 條：使用 `uv` 管理依賴  
✅ 符合子法 DDD 架構：Domain 不依賴外部實作  
✅ 符合憲法第 7.3 條：必要時重構外部邏輯以符合架構

---

## 參考資料

- LightRAG PyPI: https://pypi.org/project/lightrag-hku/
- HGMem arXiv: doc_2512_23959v2_2526f6
- DDD Bylaw: `.github/bylaws/ddd-architecture.md`
