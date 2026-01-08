# Changelog

所有重要變更都會記錄在此檔案中。

格式基於 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)，
專案遵循 [語義化版本](https://semver.org/lang/zh-TW/)。

## [0.7.0] - 2026-01-08

### Added

- **Python 3.12 升級** 🚀
  - 使用 `uv` 管理 Python 版本，釘選為 3.12.12。
  - 恢復現代 Python 語法，全面使用 PEP 604 `|` Union 標註。
- **型別系統現代化**
  - 修復了全專案的 Lint 錯誤（包括 `engine.py`, `mcp_server.py`, `persistence` 等）。
  - 在關鍵適配器中加入 `cast` 標註，提升代碼穩健性與 IDE 支援。

### Changed

- 優化 `engine.py` 的 LLM 函數簽名，解耦系統提示詞處理。
- 升級 `README.md` 環境配置，優先推薦使用 `uv sync`。

## [0.6.0] - 2026-01-07

### Added

- **Hypergraph Chain Expansion** 🎉 - 長 RAG 鏈多跳推理核心功能
  - `_expand_via_hypergraph()` 方法實現 2-hop BFS traversal
  - `_extract_seed_entities()` 從查詢和上下文提取種子實體
  - 通過 Memory Points 建立的 n-ary hyperedges 發現間接相關實體
- **Memory Points 持久化** - SQLite 存儲
  - `memory_points` 和 `subquery_history` 表結構
  - 啟動時自動載入已存在的 Memory Points
  - 查詢後自動保存新的 Memory Points
- **MCP Server v0.6.0** - 22 個完整工具
  - Document Tools: `insert_document`, `insert_text`, `insert_batch`
  - Query Tools: `query`, `query_simple`, `query_data`, `export_data`
  - Memory Tools: `evolve_memory`, `get_memory_context`, `clear_memory_points`
  - Graph Tools: `get_entity_info`, `get_relation_info`, `get_knowledge_graph`, `get_graph_stats`
  - KG Management: `insert_custom_kg`, `delete_document`, `delete_entity`
  - System Tools: `get_health`, `clear_cache`

### Fixed

- 修復 MCP LightRAG "not available" 問題 (`.vscode/mcp.json` 環境變數配置)
- 修復 Ollama LLM `'hashing_kv'` KeyError (改用 `_ollama_model_if_cache`)
- 修復 `get_memory_context` coroutine 序列化錯誤 (添加 `await`)

### Changed

- License 從 MIT 變更為 Apache 2.0

## [0.5.0] - 2026-01-06

### Added

- **EnhancedMemoryEvolver** 完整 HGMem 功能
  - `evolve_and_track()` - 演化 + 追蹤歷史
  - `reorganize_memory()` - 記憶重組/合併
  - `get_extended_info()` - 鄰居擴展上下文
- **Adapters 架構**
  - `LightRAGKGAdapter` - 連接 LightRAG Knowledge Graph
  - `VectorStoreAdapter` - 向量庫統一介面
  - `TextChunksAdapter` - KV + Vector 組合存儲
- **Domain Services**
  - `KGMemorySyncService` - collect_absent_entities_relationships()
  - `MemoryPointwiseRetriever` - get_memory_pointwise_related_info()
- **SQLiteHypergraphRepository** - 超圖持久化存儲
- 27 個測試通過 (13 E2E + 14 整合)

## [0.4.0] - 2026-01-05

### Added

- Ollama 整合 (使用 LightRAG 內建支援)
- 視覺化模組 (`HypergraphVisualizer`, `QueryPathVisualizer`)

### Removed

- 移除冗餘依賴 (`faiss-cpu`, `sentence-transformers`)

## [0.3.0] - 2025-12-20

### Added

- `HyperNode` / `HyperEdge` 實體定義
- `MemoryEvolver` 基礎版本
- `QueryProcessor` 框架
- `RAGEngine` 統一入口

## [0.2.0] - 2025-12-17

### Added

- DDD 架構建立 (Domain/Application/Infrastructure)
- Memory Bank 系統
- Claude Skills 基礎架構

## [0.1.0] - 2025-12-15

### Added

- 初始化專案結構
- 新增 Claude Skills 支援
  - `git-doc-updater` - Git 提交前自動更新文檔技能
- 新增 Memory Bank 系統
  - `activeContext.md` - 當前工作焦點
  - `productContext.md` - 專案上下文
  - `progress.md` - 進度追蹤
  - `decisionLog.md` - 決策記錄
  - `projectBrief.md` - 專案簡介
  - `systemPatterns.md` - 系統模式
  - `architect.md` - 架構文檔
- 新增 VS Code 設定
  - 啟用 Claude Skills
  - 啟用 Agent 模式
  - 啟用自定義指令檔案
