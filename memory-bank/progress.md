# Progress (Updated: 2026-02-15)

## Done

- Upgrade project to Python 3.12 via uv
- Modernize type hinting using PEP 604 (pipe syntax) across codebase
- Fix linting errors and logic bugs in engine.py and mcp_server.py
- Standardize LLM function signatures for system prompt handling
- Perform widespread code cleanup using Ruff
- **v0.7.1: Pre-commit Hooks 系統** (2026-02-15)
  - 18 個 hooks (trailing-whitespace, ruff, mypy, bandit, DDD check, skills check 等)
  - 自定義腳本: `check_ddd_deps.py`, `check_skills.py`
  - pre-push 階段測試
- **VS Code MCP 配置** (2026-02-15)
  - `.vscode/mcp.json` 支援 uv + inputs 自動參數
  - 5 個可配置輸入 (預設 Ollama)
- **測試修復** (2026-02-15)
  - SQLiteHypergraphRepository → SQLiteUnifiedRepository 重命名
  - get_stats() 回傳格式對齊
  - 26/27 測試通過
- **Lint 全面修復** (2026-02-15)
  - ruff: E731, F841, C401, SIM103, B008 等
  - mypy: 漸進式嚴格配置
  - bandit: 安全掃描通過

## Doing

- 提交代碼並推送至 GitHub

## Next

- Implement basic reranker for multi-hop expanded entities
- Add metadata provenance for Memory Points in SQLite repository
- Subgraph extraction in QueryProcessor
- query_explain Tool (推理路徑視覺化)
