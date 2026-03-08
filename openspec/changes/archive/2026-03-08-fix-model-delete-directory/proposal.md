## Why

`ModelManager.delete_model()` 只嘗試刪除單一檔案（`info.filename`），但 HuggingFace repo 下載流程（`_download_hf_repo`）建立的是目錄而非 `.zip` 檔案。導致刪除操作找不到 `.zip` 檔案而直接回傳 `False`，模型目錄仍保留在磁碟上。由於 `is_downloaded()` 會檢查目錄存在，模型仍出現在語音/LLM 設定的下拉選單中，使用者以為已刪除但實際上未刪除。

## What Changes

- 修改 `ModelManager.delete_model()` 使其同時處理檔案型與目錄型模型
  - 對 `.zip` 類型的 filename，額外嘗試刪除去掉 `.zip` 後綴的目錄（使用 `shutil.rmtree()`）
  - 使用 `dest.is_file()` 替代 `dest.exists()` 避免在目錄上呼叫 `unlink()`
- 新增目錄型模型刪除的單元測試

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `model-download`: 新增 `delete_model()` 對目錄型模型（HF repo 下載）的刪除支援

## Impact

- 受影響程式碼：`airtype/utils/model_manager.py`（`delete_model` 方法）
- 受影響測試：`tests/test_model_manager.py`（新增測試案例）
- 相關 UI 行為：`settings_models.py`、`settings_voice.py`、`settings_llm.py` 的模型列表將正確反映刪除結果（無需修改 UI 程式碼）
