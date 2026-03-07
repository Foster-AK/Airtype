## 1. HuggingFace Token Authentication 核心實作

- [x] [P] 1.1 在 `airtype/utils/model_manager.py` 新增 `_get_hf_token() -> Optional[str]` 方法，依 HF Token 來源優先順序（keyring → HF_TOKEN 環境變數 → ~/.cache/huggingface/token）取得 token。確保 Token value not logged — 僅以 DEBUG 記錄是否找到 token。
- [x] [P] 1.2 修改 `_download_url()` 的 headers 建構區塊（Authorization Header 注入點），偵測 `huggingface.co` URL 時呼叫 `_get_hf_token()` 並注入 `Authorization: Bearer <token>` header。非 HuggingFace URL 不受影響。
- [x] 1.3 修改 `download()` 方法中組裝 `all_urls` 的邏輯（無 Token 時直接走 Fallback URL）：呼叫 `_get_hf_token()`，若無 token 且 `fallback_urls` 非空，則將 `all_urls` 設為 `fallback_urls`（跳過主 HuggingFace gated URL）；若有 token 或無 fallback 則維持現行 `urls + fallback_urls` 串接邏輯。

## 2. Fallback URL 策略

- [x] 2.1 更新 `models/manifest.json`，為 gated model（qwen3-asr-*）在 `fallback_urls` 加入公開 mirror URL（Fallback URL 策略）。需先確認 ModelScope 或其他 mirror 上 Qwen3-ASR 系列的公開下載 URL 是否存在、打包格式是否一致（影響 SHA-256 校驗）。若無可用 mirror 則留空並在 README 註明。

## 3. HuggingFace Token UI 欄位與 401 Error Guidance

- [x] 3.1 在 `airtype/ui/settings_models.py` 的模型管理頁面頂端新增 HF Access Token 輸入區域（HuggingFace Token UI 欄位）：密碼遮罩 `QLineEdit` + 清除按鈕 + 說明文字（引導使用者前往 huggingface.co 取得 token，說明未填寫時自動改用公開 Mirror）。輸入後觸發 `config.set_api_key("huggingface", token)`，清除後觸發 `config.set_api_key("huggingface", "")`。
- [x] 3.2 修改 `airtype/ui/settings_models.py` 的 `_on_download_error()` 下載失敗處理邏輯（401 錯誤 UI 提示（保底機制））：檢查 error 字串是否包含 `"401"`（httpx.HTTPStatusError 的 `__str__()` 包含狀態碼數字），若是則將 QMessageBox 訊息替換為 HF token 設定引導文字，告知使用者可在此頁面的 Token 欄位輸入 HuggingFace Access Token。

## 4. 測試

- [x] [P] 4.1 為 `_get_hf_token()` 撰寫單元測試：測試 keyring 有 token、僅環境變數有 token、僅快取檔有 token、三者皆無等情境（驗證 HuggingFace Token Authentication spec 所有 scenario）。
- [x] [P] 4.2 為 `_download_url()` 撰寫測試：驗證 HuggingFace URL 帶 Authorization header、非 HuggingFace URL 不帶 header（驗證 Non-HuggingFace URL unaffected scenario）。
- [x] [P] 4.3 為 HuggingFace Token UI 欄位撰寫測試：驗證輸入 token 後存入 keyring、清除後移除 keyring（驗證 HuggingFace Token Input spec 所有 scenario）。
- [x] 4.4 驗證 401 錯誤時 UI 顯示正確引導訊息（HuggingFace 401 Error Guidance），非 401 錯誤顯示標準訊息。
