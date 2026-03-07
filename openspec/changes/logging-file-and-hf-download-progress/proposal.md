## Why

使用者執行打包後的 `airtype.exe` 下載模型時，進度一直停在 0%，且無任何錯誤訊息可供診斷。根本原因有二：

1. **日誌不可見**：`logging_setup.py` 只輸出到 `sys.stderr`，但 PyInstaller 打包時 `console=False`，stderr 無終端接收，所有日誌全部消失。
2. **HF repo 下載無中間進度**：manifest 中多數 ASR 模型 URL 為 HuggingFace repo URL（非 `/resolve/` 直連），走 `snapshot_download()` 路徑，只發送 0% 和 100%，中間無任何進度回報。

## What Changes

- 在 `setup_logging()` 中新增 `RotatingFileHandler`，將日誌寫入 `~/.airtype/logs/airtype.log`（5MB 輪替，保留 3 份備份），檔案 handler 固定 DEBUG 等級
- 在 `_download_hf_repo()` 中透過 `huggingface_hub.snapshot_download()` 的 `tqdm_class` 參數注入自訂進度追蹤器，將內部逐 chunk 進度轉為 `progress_callback` 呼叫

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `model-download`：HuggingFace repo 下載現在需回報中間進度（而非僅 0% 和 100%）
- `project-structure`：日誌系統新增檔案輸出（RotatingFileHandler → `~/.airtype/logs/`）

## Impact

- 受影響程式碼：`airtype/logging_setup.py`、`airtype/utils/model_manager.py`
- 受影響規格：`model-download`、`project-structure`
- 新增依賴：無（`RotatingFileHandler` 為 Python 標準庫；`tqdm_class` 為 `huggingface_hub` 既有參數）
- 相依 change：無（獨立修復）
