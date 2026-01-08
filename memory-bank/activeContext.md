# Active Context

## Current Status
- ✅ **Python 3.12 升級完成**：全面使用 `uv` 管理與恢復 `|` 標註。
- ✅ **代碼現代化修復**：修復了 `engine.py`, `mcp_server.py`, `persistence` 等 20+ 個檔案的型別與邏輯錯誤。
- 🔄 **準備提交環境變更**。

## Current Goals
- [x] 升級 Python 3.12 並釘選版本。
- [x] 修復所有 `mypy` 和 `ruff` 偵測到的型別不相容問題。
- [x] 恢復 Python 3.10+ 的簡潔 Union 語法 (`|`)。
- [ ] 執行完整的 E2E 驗證（待環境穩定後）。

## Architecture Decision Log (Update)

### 決策：全面轉向 Python 3.12 現代語法
- **背景**: 之前為了相容性改回 `Union/Optional`。
- **決策**: **恢復 PEP 604 語法**。
- **原因**: 專案已決定使用 `uv` 鎖定 Python 3.12+，無須再為舊版本做語法妥協，現代語法更易於閱讀與維護。

## Implemented Components

### Domain Layer
- `HyperNode`: 支援 `|` 語法標註。
- `KGMemorySyncService`: 修正了 `None` 賦值邏輯與 Lambda 描述函數。

### Infrastructure Layer
- `SQLiteUnifiedRepository`: 補全 `Generator` 標註。
- `Adapters`: 加入 `cast` 處理外部庫返回的 `Any` 型別。

### Application Layer
- `RAGEngine`: 修正 LLM 初始化邏輯與實體選取。

## Next Steps
- 提交代碼並推送至 GitHub。
- 測試 `RAGEngine` 的 `STORAGE_TYPE` 動態切換。
- 實作超圖擴展實體的 Reranker。
