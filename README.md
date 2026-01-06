# HyperHierarchicalRAG

> **結合超圖記憶 (Hypergraph Memory) 與階層式檢索 (Hierarchical Retrieval) 的新型 RAG 系統**
> 
> 透過 MCP (Model Context Protocol) 將知識檢索能力暴露給 AI Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

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
│                   MCP Layer (Agent Interface)                   │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │query_hybrid│ │insert_doc  │ │evolve_memory │ │ get_graph  │ │
│  └────────────┘ └────────────┘ └──────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │   QueryProcessor    │     │      MemoryManager          │   │
│  │ (Hierarchical +     │     │ (Hypergraph Evolution)      │   │
│  │  Hypergraph Query)  │     │                             │   │
│  └─────────────────────┘     └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┴──────────────────┐
           ▼                                     ▼
┌─────────────────────────┐       ┌─────────────────────────────┐
│    Infrastructure       │       │       Domain Layer          │
│  (LightRAG Adapter)     │       │    (HGMem Core Logic)       │
│                         │       │                             │
│ • HierarchicalRouter    │       │ • HyperNode / HyperEdge     │
│ • KeywordExtractor      │       │ • MemoryEvolver             │
│ • KnowledgeGraph        │       │ • WorkingMemory             │
└─────────────────────────┘       └─────────────────────────────┘
```

## ✨ 核心特性

### 🔍 階層式檢索 (from LightRAG)
- **Local Keywords**: 實體級別的精確檢索
- **Global Keywords**: 主題級別的語義檢索
- **Hybrid Mode**: 結合關鍵字與向量檢索

### 🕸️ 超圖記憶 (from HGMem)
- **HyperEdge**: 支援 n-ary 關係（超越傳統二元關係）
- **Memory.evolve()**: 記憶自適應演化機制
- **Working Memory**: 多步推理的上下文保持

### 🔌 MCP 整合 (inspired by lightrag-mcp)
- **文本 CRUD**: `insert_document`, `get_documents`, `delete_document`
- **知識查詢**: `query_hybrid`, `query_local`, `query_global`
- **圖譜操作**: `create_entities`, `create_relations`, `evolve_memory`

## 🚀 快速開始

### 環境設置

```bash
# 1. Clone 專案
git clone https://github.com/u9401066/hyperhierarchical-rag.git
cd hyperhierarchical-rag

# 2. 建立虛擬環境
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1  # Windows

# 3. 安裝依賴
uv pip install -e ".[dev]"

# 4. 安裝 external 依賴
uv pip install -e ./external/LightRAG
```

### 作為 MCP Server 使用

```json
{
  "mcpServers": {
    "hyperhierarchical-rag": {
      "command": "uv",
      "args": ["--directory", "/path/to/project", "run", "hyperhierarchical-rag"],
      "env": { "OPENAI_API_KEY": "your-api-key" }
    }
  }
}
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

### lightrag-mcp
- **Repository**: [shemhamforash23/lightrag-mcp](https://github.com/shemhamforash23/lightrag-mcp)
- **用途**: MCP Server 架構參考

## 📁 專案結構

```
hyperhierarchical-rag/
├── src/hyperhierarchical_rag/
│   ├── domain/              # HGMem 核心邏輯
│   ├── infrastructure/      # LightRAG Adapter
│   ├── application/         # Use Cases
│   └── mcp_server.py        # MCP Tools
├── external/                # 外部依賴
│   ├── LightRAG/
│   ├── HGMem/
│   └── lightrag-mcp/
├── docs/architecture/
├── memory-bank/
└── tests/
```

## 📋 開發文檔

- [CONSTITUTION.md](CONSTITUTION.md) - 專案最高原則
- [docs/ROADMAP.md](docs/ROADMAP.md) - 開發路線圖
- [docs/architecture/](docs/architecture/) - 架構設計文檔

## 📄 License

MIT License
