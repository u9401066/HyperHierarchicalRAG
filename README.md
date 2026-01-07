# HyperHierarchicalRAG

> **結合超圖記憶 (Hypergraph Memory) 與階層式檢索 (Hierarchical Retrieval) 的新型 RAG 系統**
> 
> 透過 MCP (Model Context Protocol) 將知識檢索能力暴露給 AI Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Version](https://img.shields.io/badge/version-0.6.0-brightgreen.svg)](CHANGELOG.md)

🌐 [繁體中文](README.zh-TW.md)

## 🎯 專案目標

整合兩個強大的 RAG 系統，創建一個功能完整的知識檢索平台：

| 來源 | 功能 | 核心技術 |
|------|------|----------|
| **[LightRAG](https://github.com/HKUDS/LightRAG)** | 階層式關鍵字檢索 | Local/Global Keywords |
| **[HGMem](https://github.com/Jiaqi-Chen-00/HGMem)** | 超圖工作記憶體 | Hypergraph + Memory.evolve() |
| **[lightrag-mcp](https://github.com/shemhamforash23/lightrag-mcp)** | MCP Server 架構 | FastMCP + Tools |

## 🏗️ 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                   MCP Layer (22 Tools)                          │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │   query    │ │insert_doc  │ │evolve_memory │ │ get_graph  │ │
│  └────────────┘ └────────────┘ └──────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      RAGEngine (Unified API)                     │
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │   QueryProcessor    │     │  EnhancedMemoryEvolver      │   │
│  │ (Hierarchical +     │     │ (Hypergraph Chain +         │   │
│  │  Hypergraph Query)  │     │  Memory Persistence)        │   │
│  └─────────────────────┘     └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┴──────────────────┐
           ▼                                     ▼
┌─────────────────────────┐       ┌─────────────────────────────┐
│    Infrastructure       │       │       Domain Layer          │
│  (LightRAG Adapters)    │       │    (HGMem Core Logic)       │
│                         │       │                             │
│ • LightRAGKGAdapter     │       │ • HyperNode / HyperEdge     │
│ • VectorStoreAdapter    │       │ • MemoryEvolver             │
│ • TextChunksAdapter     │       │ • SQLiteHypergraphRepo      │
└─────────────────────────┘       └─────────────────────────────┘
```

## ✨ 核心特性

### 🔍 階層式檢索 (from LightRAG)

- **Local Keywords**: 實體級別的精確檢索
- **Global Keywords**: 主題級別的語義檢索
- **Hybrid Mode**: 結合關鍵字與向量檢索

### 🗄️ 雙路儲存架構 (Dual-Path Storage) - [NEW!]

- **Local-Fast 模式**: 基於 **SQLite** 的一站式儲存。將 KG (圖譜)、Memory (超圖記憶) 與 Chunks (文本與元數據) 整合進單個 SQLite 檔案，實現事務一致性與零配置啟動。
- **Enterprise 模式**: 支援 **Milvus** / **PostgreSQL** / **Neo4j** 分散式後端，滿足大規模預算與高併發需求。

### �🕸️ 超圖記憶 (from HGMem)

- **HyperEdge**: 支援 n-ary 關係（超越傳統二元關係）
- **Memory.evolve()**: 記憶自適應演化機制
- **Hypergraph Chain**: 長 RAG 鏈多跳推理 (2-hop BFS traversal)
- **Memory Persistence**: SQLite 持久化記憶點

### 🔌 MCP 整合 (22 Tools)

- **文本 CRUD**: `insert_document`, `insert_text`, `insert_batch`
- **知識查詢**: `query`, `query_simple`, `query_data`
- **記憶操作**: `evolve_memory`, `get_memory_context`, `clear_memory_points`
- **圖譜操作**: `get_entity_info`, `get_relation_info`, `get_knowledge_graph`
- **系統工具**: `get_health`, `get_graph_stats`, `clear_cache`

## 🚀 快速開始

### 環境設置

```bash
# 1. Clone 專案
git clone https://github.com/u9401066/HyperHierarchicalRAG.git
cd HyperHierarchicalRAG

# 2. 建立虛擬環境 (使用 uv)
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate     # Linux/Mac

# 3. 安裝依賴
uv pip install -e ".[dev]"

# 4. 安裝 external LightRAG
uv pip install -e ./external/LightRAG
```

### 環境變數配置

```bash
# .env 範例
LLM_PROVIDER=ollama           # 或 openai
LLM_MODEL=llama3.1:8b
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
OLLAMA_HOST=http://localhost:11434

# 或使用 OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your-api-key
# LLM_MODEL=gpt-4o-mini
```

### 作為 MCP Server 使用

`.vscode/mcp.json`:

```json
{
  "servers": {
    "hyperhierarchical-rag": {
      "command": "uv",
      "args": ["--directory", "c:/workspace260106", "run", "hyperhierarchical-rag"],
      "env": {
        "LLM_PROVIDER": "ollama",
        "LLM_MODEL": "llama3.1:8b",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "EMBEDDING_DIM": "768"
      }
    }
  }
}
```

### Python API 使用

```python
import asyncio
from hyperhierarchical_rag.engine import RAGEngine

async def main():
    # 初始化
    engine = RAGEngine.from_env()
    await engine.initialize()
    
    # 插入文檔
    await engine.insert_document("RAG combines retrieval with generation...")
    
    # 查詢 (帶記憶演化)
    result = await engine.query(
        query="What is RAG?",
        mode="hybrid",
        evolve_memory=True
    )
    
    print(result["lightrag_response"])
    print(f"Memory Points: {len(engine._memory_evolver.memory_points)}")
    
    # Hypergraph Chain Expansion 會自動發現相關實體
    if "hypergraph_expanded" in result:
        print(f"Discovered: {result['hypergraph_expanded']['discovered_entities']}")

asyncio.run(main())
```

## 🧠 Hypergraph Chain Expansion

HGMem 的核心價值 - **長 RAG 鏈多跳推理**：

```
╔═══════════════════════════════════════════════════════════════════════╗
║ LightRAG binary edges:   A ─── B ─── C                                ║
║                         (只能一次遍歷一條邊)                          ║
║                                                                        ║
║ HGMem hyperedges:   {A, B, C, D} 全部在同一超邊中                      ║
║                         (即使從 A 查詢也能發現 D！)                    ║
╚═══════════════════════════════════════════════════════════════════════╝
```

**範例**：
- 查詢: `"knowledge graph LLM"`
- LightRAG 找到: Knowledge Graph → enhances → LLM
- **Hypergraph 額外發現**: `IMPROVED RETRIEVAL`, `CONTEXTUAL UNDERSTANDING` (不在直接路徑中！)

## 📊 測試狀態

```bash
# 執行所有測試
uv run pytest tests/ -v

# 測試結果: 27 tests passed
# - 13 E2E tests
# - 14 Integration tests
```

## 📚 引用 (Citations)

本專案整合並參考了以下優秀的開源專案：

### LightRAG
```bibtex
@article{guo2024lightrag,
  title={LightRAG: Simple and Fast Retrieval-Augmented Generation},
  author={Guo, Zirui and Liang, Lianghao and Long, Guodong and others},
  journal={arXiv preprint arXiv:2410.05779},
  year={2024}
}
```

### HGMem (Hypergraph Memory)
```bibtex
@article{chen2024hgmem,
  title={HGMem: Heterogeneous Graph Memory for Long-range Dependencies},
  author={Chen, Jiaqi and others},
  journal={arXiv preprint arXiv:2512.23959},
  year={2024}
}
```

## 📁 專案結構

```
HyperHierarchicalRAG/
├── src/hyperhierarchical_rag/
│   ├── Domain/              # HGMem 核心邏輯
│   │   ├── entities.py      # HyperNode, HyperEdge
│   │   └── services/        # MemoryEvolver
│   ├── Infrastructure/      # LightRAG Adapters
│   │   ├── adapters/        # KG, Vector, TextChunks
│   │   └── persistence/     # SQLiteHypergraphRepository
│   ├── Application/         # Use Cases
│   │   ├── query_processor.py
│   │   └── memory_manager.py
│   ├── engine.py            # RAGEngine 統一入口
│   └── mcp_server.py        # MCP Server (22 Tools)
├── external/                # 外部依賴
│   └── LightRAG/
├── data/                    # 運行時數據
│   ├── lightrag/            # LightRAG KG + VectorDB
│   └── hypergraph/          # Memory Points SQLite
├── memory-bank/             # Claude Memory Bank
├── tests/                   # 測試套件
└── scripts/                 # 工具腳本
```

## 📋 開發文檔

- [CHANGELOG.md](CHANGELOG.md) - 版本變更記錄
- [ROADMAP.md](ROADMAP.md) - 開發路線圖
- [CONSTITUTION.md](CONSTITUTION.md) - 專案最高原則
- [docs/architecture/](docs/architecture/) - 架構設計文檔

## 🤝 Contributing

歡迎貢獻！請參閱 [CONTRIBUTING.md](CONTRIBUTING.md) 了解詳情。

## 📄 License

Apache License 2.0 - 詳見 [LICENSE](LICENSE)

---

**Made with ❤️ by HyperHierarchicalRAG Contributors**
