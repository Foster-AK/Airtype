## Context

目前 `ModelManager._download_url()`（`airtype/utils/model_manager.py:345`）僅發送 `Range` header 用於斷點續傳，不帶任何認證資訊。HuggingFace 上的 gated model（如 Qwen3-ASR 系列）回傳 HTTP 401 Unauthorized，導致所有 gated model 下載失敗。

現有 `airtype/config.py` 已提供 `get_api_key(provider)` / `set_api_key(provider, key)` 透過系統 keyring 儲存 API 金鑰的機制，可直接復用於 HuggingFace token。

## Goals / Non-Goals

**Goals:**

- 下載 `huggingface.co` URL 時自動偵測並附加 `Authorization: Bearer <token>` header
- 支援三層 token 來源：keyring（`provider="huggingface"`）→ 環境變數 `HF_TOKEN` → `~/.cache/huggingface/token`
- 為 gated model 在 `manifest.json` 加入公開 mirror fallback URL
- 401 錯誤時在 UI 顯示明確的 token 設定引導

**Non-Goals:**

- 不實作 HuggingFace OAuth 登入流程
- 不修改非 HuggingFace URL 的下載行為

## Decisions

### HF Token 來源優先順序

在 `ModelManager` 新增私有方法 `_get_hf_token() -> Optional[str]`，依序嘗試：

1. `config.get_api_key("huggingface")` — 系統 keyring（最安全、使用者明確設定）
2. `os.environ.get("HF_TOKEN")` — 環境變數（CI/CD 環境常用）
3. `Path.home() / ".cache" / "huggingface" / "token"` — huggingface-cli 登入後自動產生的快取檔

**理由**：keyring 優先因為是加密儲存且為專案既有模式；環境變數是 HuggingFace 官方推薦方式；快取檔是 `huggingface-cli login` 的產物，支援此來源可讓已登入的使用者無需額外設定。

**替代方案**：僅支援環境變數 — 但這對一般桌面使用者不友善，keyring 整合更符合專案慣例。

### Authorization Header 注入點

修改 `_download_url()` 的 headers 建構區塊（第 378 行），在組裝 headers dict 時檢查 URL 是否包含 `huggingface.co`，若是則注入 `Authorization` header。

**理由**：最小修改幅度，僅影響 headers 組裝邏輯，不改變下載流程本身。

### Fallback URL 策略

在 `manifest.json` 的 `fallback_urls` 欄位加入 HuggingFace Mirror 或 ModelScope 上的公開 URL。Token 認證僅在主 URL 使用；fallback URL 若為非 HuggingFace 網域則不帶 token。

**理由**：雙重保障 — 有 token 的使用者走主 URL，無 token 的使用者走 fallback。

### HuggingFace Token UI 欄位

在 `settings_models.py` 的模型管理頁面頂端新增 HF Access Token 輸入區域：

- 欄位型式：`QLineEdit`（`echoMode=Password`，密碼遮罩顯示）+ 清除按鈕
- 說明文字：引導使用者前往 huggingface.co 取得 token，並說明若未填寫則自動改用公開 Mirror 下載
- 儲存機制：輸入後自動呼叫 `config.set_api_key("huggingface", token)` 存入系統 keyring；清除時呼叫 `config.set_api_key("huggingface", "")` 移除
- Token 欄位為選填（optional），一般使用者可跳過
- 初始化行為：頁面載入時呼叫 `config.get_api_key("huggingface")`，若有值則在欄位顯示遮罩佔位符（如 `hf_****`）表示已設定，不顯示明文；若無值則欄位留空並顯示 placeholder 提示文字

**理由**：讓 token 設定成為應用程式內的一等功能，而非事後的故障排除步驟。有 token 的使用者直接在 UI 填入；無 token 的使用者自動走公開 Mirror，不會遇到 401 錯誤。

**替代方案**：僅在 401 發生後顯示提示訊息 — 但這造成「先失敗再引導」的差劣 UX；主動提供 UI 欄位更符合零障礙設計原則。

### 無 Token 時直接走 Fallback URL

修改 `download()` 方法中組裝 `all_urls` 的邏輯（現行為 `list(info.urls) + list(info.fallback_urls)` 逐一重試）：呼叫 `_get_hf_token()`，若無 token 且主 URL 包含 `huggingface.co` 且 `fallback_urls` 非空，則將 `all_urls` 設為 `fallback_urls`，跳過主 HuggingFace gated URL。若有 token 或無 fallback，維持現行串接邏輯。

**理由**：對無 token 的使用者，直接走公開 Mirror 比嘗試失敗再 fallback 更有效率，也避免無意義的 401 錯誤。判斷點在 `download()` 而非 `_download_url()`，因為 URL 選擇是模型層級的全局決策。若 `fallback_urls` 也為空，才回退至原始 URL 並保留 401 錯誤提示。

### 401 錯誤 UI 提示（保底機制）

在 `settings_models.py` 的 `DownloadWorker` 下載失敗處理中，偵測錯誤訊息包含 `401` 時，在 UI 顯示提示文字引導使用者設定 HF token。

**理由**：作為最後一道保底 — 當 `fallback_urls` 也缺失時，仍能給使用者明確指引。

## Risks / Trade-offs

- **[Token 外洩風險]** → 不在 log 中記錄 token 值；僅以 `logger.debug("已附加 HF token")` 記錄是否使用 token
- **[Mirror URL 可用性]** → fallback URL 可能過期或不同步；SHA-256 驗證可確保下載完整性
- **[Windows 路徑差異]** → `~/.cache/huggingface/token` 在 Windows 上為 `%USERPROFILE%\.cache\huggingface\token`；使用 `Path.home()` 確保跨平台一致
- **[UI 密碼欄位顯示]** → 使用者可能不理解為何要填寫 token；說明文字需清楚引導，並強調此欄位為選填
