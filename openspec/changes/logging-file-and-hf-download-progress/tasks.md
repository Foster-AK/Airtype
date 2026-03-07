## 1. RotatingFileHandler 輪替策略 — Structured Logging 檔案輸出

- [x] [P] 1.1 實作 Structured Logging 檔案輸出：在 `airtype/logging_setup.py` 的 `setup_logging()` 中新增 `RotatingFileHandler`，寫入 `~/.airtype/logs/airtype.log`（5MB 上限、3 份備份、UTF-8 編碼），檔案 handler 固定 DEBUG 等級，套用 `SanitizingFilter`。包含 log file handler failure 的 try/except 容錯（失敗時 stderr 警告，不中斷啟動）。驗證：啟動應用程式後 `~/.airtype/logs/airtype.log` 存在且包含 `[INFO]` 等級的啟動訊息。

- [x] [P] 1.2 撰寫 `tests/test_logging_setup.py` 單元測試：驗證 log file creation（首次啟動建立目錄與檔案）、log file rotation（超過 5MB 時輪替）、log file available in packaged application（無 console 時檔案仍可寫入）、log file handler failure（磁碟權限錯誤時不中斷）。驗證：`pytest tests/test_logging_setup.py` 全部通過。

## 2. tqdm_class 進度轉接器 — HuggingFace repo 下載進度

- [x] 2.1 在 `airtype/utils/model_manager.py` 中建立 `_SharedProgress` 類別與 `_HfProgressAdapter` 類別（tqdm-compatible wrapper），實作多 tqdm 實例的進度彙總。`_HfProgressAdapter` 需實作 `__init__(total=)`, `update(n)`, `close()`, `__enter__`, `__exit__`, `set_description`, `set_postfix` 等 tqdm 最小 API。驗證：可被 `snapshot_download(tqdm_class=...)` 正常呼叫。

- [x] 2.2 修改 `_download_hf_repo()` 方法，當 `progress_callback` 存在時透過 `functools.partial` 將 callback 綁定到 `_HfProgressAdapter`，作為 `tqdm_class` 參數傳入 `snapshot_download()`。HuggingFace repo download reports intermediate progress：callback 在每個 chunk 接收時被呼叫，包含彙總的 downloaded bytes、total bytes、percentage、ETA。HuggingFace repo download without callback：無 callback 時不注入 tqdm_class。驗證：在設定面板下載 HF repo 模型時，進度條持續更新。

- [x] [P] 2.3 撰寫 `tests/test_model_manager_hf_progress.py` 單元測試：mock `snapshot_download` 並驗證 `_HfProgressAdapter` 正確彙總多檔案進度、callback 被呼叫多次且百分比遞增、無 callback 時不注入 tqdm_class。驗證：`pytest tests/test_model_manager_hf_progress.py` 全部通過。

## 3. 端對端驗證

- [x] 3.1 手動端對端測試：執行 `python -m airtype` 確認 `~/.airtype/logs/airtype.log` 產生且 model download with progress 的日誌訊息完整；在設定面板下載一個 HF repo 模型，確認進度條持續更新而非卡在 0%。驗證：日誌檔存在、進度條正常遞增。
