# HyperHierarchicalRAG 快速開始

## 環境設置

### 1. 啟動虛擬環境

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# 或使用 cmd
.\.venv\Scripts\activate.bat
```

### 2. 安裝依賴

```bash
# 安裝所有依賴（包含開發工具）
uv pip install -e ".[dev]"

# 僅安裝生產依賴
uv pip install -e .
```

### 3. 驗證安裝

```bash
# 執行測試
pytest

# 檢查程式碼品質
ruff check src/
black --check src/
mypy src/
```

## 依賴管理策略

請參閱 [docs/architecture/dependency-strategy.md](docs/architecture/dependency-strategy.md) 了解我們如何整合：
- **LightRAG** (PyPI): 階層式關鍵字抽取
- **HGMem** (核心邏輯): 超圖記憶演化

## 開發工作流

1. **建立新分支**: `git checkout -b feature/your-feature`
2. **開發與測試**: 參考 `.github/bylaws/` 中的規範
3. **提交前檢查**: 使用 `GIT` skill 或執行 pre-commit 檢查清單
4. **提交**: `git commit -m "feat: your feature"`

## 架構概覽

```
src/
├── Domain/              # 核心業務邏輯（HGMem 邏輯整合於此）
├── Application/         # 用例與應用服務
├── Infrastructure/      # DAL + 外部服務（LightRAG Adapter）
└── Presentation/        # API 或 CLI
```

詳見：[docs/architecture/data-model.md](docs/architecture/data-model.md)
