## Why

HuggingFace 上的 gated model（如 Qwen3-ASR 系列）需要認證才能下載，但目前 `ModelManager._download_url()` 不帶任何 Authorization header，導致所有 gated model 下載回傳 HTTP 401 Unauthorized 並失敗。使用者無法透過現有機制提供 HuggingFace token。

## What Changes

- **model_manager.py**：新增 HuggingFace token 自動偵測與注入機制。下載 `huggingface.co` URL 時自動帶上 `Authorization: Bearer <token>` header。Token 來源優先順序：keyring → 環境變數 `HF_TOKEN` → `~/.cache/huggingface/token` 快取檔。
- **manifest.json**：為 gated model 加入公開 mirror fallback URL（如 ModelScope），確保無 token 時仍有備用下載管道。
- **settings_models.py**：在模型管理頁面新增 HF Access Token 輸入欄位（密碼遮罩、清除按鈕），讓使用者可在 app 內直接設定 token 並存入 keyring。下載失敗且錯誤為 401 時，顯示提示訊息引導使用者設定 HF token（保底機制）。

## Capabilities

### New Capabilities

（無新增 capability — 此為既有模型下載功能的 bug fix）

### Modified Capabilities

- `model-download`：新增需求 — 下載 HuggingFace URL 時 SHALL 自動偵測並附加認證 token
- `settings-models`：新增需求 — 模型管理頁面 SHALL 提供 HF Token 輸入欄位；下載因 401 失敗時 SHALL 顯示 HF token 設定提示

## Impact

- 受影響程式碼：`airtype/utils/model_manager.py`、`airtype/ui/settings_models.py`、`models/manifest.json`
- 受影響 specs：`model-download`、`settings-models`
- 依賴：keyring（已存在於專案依賴）、httpx（已存在）
- 無 breaking change
