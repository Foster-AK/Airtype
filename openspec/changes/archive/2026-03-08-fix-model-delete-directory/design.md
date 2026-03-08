## Context

`ModelManager.delete_model()` 目前只處理單一檔案刪除（`Path.unlink()`），但 HuggingFace repo 下載流程（`_download_hf_repo`）將模型直接下載至目錄（如 `~/.airtype/models/qwen3-asr-0.6b-openvino/`），不會產生 `.zip` 檔案。`is_downloaded()` 已正確處理目錄檢查，但 `delete_model()` 遺漏了這一路徑，導致刪除操作無效。

受影響檔案：`airtype/utils/model_manager.py`（已 `import shutil`）。

## Goals / Non-Goals

**Goals:**

- 修正 `delete_model()` 使其能刪除檔案型與目錄型模型
- 保持與 `is_downloaded()` 和 `get_model_path()` 的邏輯一致性
- 新增對應的單元測試

**Non-Goals:**

- 不修改 UI 程式碼（刪除成功後 UI 刷新流程已正確）
- 不修改下載流程或 manifest 格式
- 不處理 config 中活躍模型引用的自動清理（現有警告機制已足夠）

## Decisions

### 使用 shutil.rmtree 刪除目錄型模型

對 `.zip` 類型的 filename，在嘗試刪除 `.zip` 檔案之後，額外檢查並刪除去掉 `.zip` 後綴的目錄。使用 `shutil.rmtree()` 遞迴刪除。

選擇 `shutil.rmtree` 而非逐檔刪除：模型目錄可能包含多層子目錄和大量檔案（如 OpenVINO IR 模型），遞迴刪除更簡潔可靠。`shutil` 已在檔案頂部 import。

### 同時嘗試刪除檔案和目錄

不以互斥方式處理，而是先嘗試刪除 `.zip` 檔案、再嘗試刪除目錄。這樣可處理三種狀態：僅有 `.zip`、僅有目錄、兩者同時存在（例如下載後解壓但未清理 `.zip`）。

### 使用 is_file() 替代 exists()

原始碼使用 `dest.exists()` 判斷，但 `exists()` 對目錄也回傳 `True`，而 `unlink()` 無法刪除目錄（會拋出 `IsADirectoryError` 或 `PermissionError`）。改用 `dest.is_file()` 更精確。

## Risks / Trade-offs

- **[風險] `shutil.rmtree` 是不可逆操作** → 刪除前已有 `QMessageBox.question` 確認對話框；`delete_model` 僅操作 `_download_dir` 內的檔案，路徑由 manifest 控制，不存在路徑注入風險。
- **[風險] 跨平台檔案鎖定** → Windows 上若模型檔案被其他程序佔用，`rmtree` 會拋出 `OSError`，已有 `except OSError` 處理並記錄日誌。
