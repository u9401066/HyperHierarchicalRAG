# 貢獻指南

感謝你有興趣為此專案做出貢獻！

## 如何貢獻

### 回報問題 (Bug Report)

1. 先搜尋現有 Issues，確認問題未被回報
2. 使用 Issue 模板提交問題
3. 提供清晰的重現步驟

### 功能建議 (Feature Request)

1. 先搜尋現有 Issues
2. 描述功能的使用場景
3. 說明期望的行為

### 提交程式碼 (Pull Request)

#### 開發流程

1. Fork 此專案
2. 建立功能分支：`git checkout -b feature/your-feature`
3. 遵循專案架構（參見 `CONSTITUTION.md`）
4. 提交變更：`git commit -m 'feat: add your feature'`
5. 推送分支：`git push origin feature/your-feature`
6. 建立 Pull Request

#### Commit 訊息格式

遵循 Conventional Commits：

```
<type>(<scope>): <subject>

<body>

<footer>
```

類型：
- `feat`: 新功能
- `fix`: 修復
- `docs`: 文檔
- `refactor`: 重構
- `test`: 測試
- `chore`: 雜項

#### 程式碼規範

- 遵循 DDD 架構（參見 `.github/bylaws/ddd-architecture.md`）
- DAL 必須獨立
- 提交前更新相關文檔

### 審查流程

1. 自動化檢查通過
2. 至少一位維護者審查
3. 所有討論已解決
4. 文檔已更新

## 行為準則

請參閱 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

## 問題？

如有任何問題，歡迎開 Issue 討論！
