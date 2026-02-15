# Decision Log

## 2026-02-15: Pre-commit Hooks 架構

- **Decision**: 建立 18 個 pre-commit hooks，分為基礎檢查、Lint/Format、型別/安全、自定義四層
- **Rationale**: 確保代碼品質可以在 commit 階段就被捕捉，減少 CI 的負擔
- **Notes**: 測試放在 pre-push 而非 pre-commit，避免 commit 太慢

## 2026-02-15: MyPy 漸進式嚴格

- **Decision**: 關閉 strict mode，先忽略 `type-arg` 和 `unused-ignore` 錯誤
- **Rationale**: 專案有 80+ 個泛型型別參數缺失，一次修完不切實際。先保留基本檢查（untyped defs、return any），待泛型標註完善後再啟用 strict

## 2026-02-15: MCP 配置採用 VS Code Inputs

- **Decision**: `.vscode/mcp.json` 使用 `inputs` 讓用戶啟動時選擇參數，預設 Ollama
- **Rationale**: 零成本本地方案， clone 後即可用。OpenAI key 用密碼遮罩

## 2026-01-08: Python 3.12 PEP 604 語法

- **Decision**: 全面恢復 `|` Union 語法、使用 `uv` 鎖定 Python 3.12+
- **Rationale**: 現代語法更易讀，uv 已確保版本一致性

## 2026-01-07: Dual-Path Storage Architecture

- **Decision**: Enterprise vs. Local-Fast SQLite 雙路儲存
- **Rationale**: 提供零配置本地可用性 (SQLite) 同時保持企業級擴展性 (Milvus/PostgreSQL)

## 2026-01-06: Project Scaffolded

- **Decision**: Used `u9401066/template-is-all-you-need` as the base
- **Rationale**: Provides solid Constitution-Bylaw-Skill structure and Memory Bank pattern
