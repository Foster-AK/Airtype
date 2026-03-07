## Context

Airtype 打包為 GUI 應用程式（PyInstaller `console=False`），日誌僅輸出到 `sys.stderr`，但無終端視窗接收 stderr，導致所有日誌在打包環境中完全不可見。此外，HuggingFace repo 模型下載使用 `huggingface_hub.snapshot_download()`，該 API 內部雖有 tqdm 進度條，但 `_download_hf_repo()` 未利用 `tqdm_class` 參數轉接，導致 UI 只收到 0% 和 100% 兩個進度點。

目前程式碼現狀：
- `airtype/logging_setup.py`：僅有一個 `StreamHandler(sys.stderr)`，全域 `_initialized` 防重複
- `airtype/utils/model_manager.py:_download_hf_repo()`：呼叫 `snapshot_download()` 無 `tqdm_class` 參數
- `airtype/utils/model_manager.py:_download_url()`：已有完整的逐 chunk 進度回報（不受影響）

## Goals / Non-Goals

**Goals:**

- 日誌自動寫入檔案 `~/.airtype/logs/airtype.log`，無論是否有終端視窗
- 檔案日誌使用 RotatingFileHandler 避免無限增長
- HuggingFace repo 下載在 UI 上顯示真實的中間進度百分比

**Non-Goals:**

- 不改變 console handler 的行為（保留 stderr 輸出）
- 不修改 `_download_url()` 的直連下載邏輯（已正常運作）
- 不新增日誌檢視 UI（使用者直接查看檔案即可）

## Decisions

### RotatingFileHandler 輪替策略

選擇 `logging.handlers.RotatingFileHandler`，單檔 5 MB、保留 3 份備份（共最多 20 MB）。

替代方案：`TimedRotatingFileHandler`（按時間輪替）。不採用，因為 Airtype 非常駐服務，使用者可能數天不啟動，按大小輪替更能控制磁碟佔用。

### 檔案 handler 固定 DEBUG 等級

檔案 handler 的等級固定為 `DEBUG`，不隨 `config.general.log_level` 變化。Console handler 等級繼續跟隨設定。

理由：檔案日誌的主要目的是事後診斷，需要最完整的資訊。使用者不需要主動管理檔案日誌等級。

### tqdm_class 進度轉接器

在 `model_manager.py` 中建立 `_HfProgressAdapter` 類別，實作 tqdm 最小 API（`__init__`, `update`, `close`, `__enter__`, `__exit__`），透過 `snapshot_download(tqdm_class=...)` 注入。

替代方案：
1. 手動列舉 repo 檔案再逐一用 `hf_hub_download()` 下載 — 過於複雜，且需處理 repo 結構解析。
2. 輪詢 `local_dir` 目錄大小 — 不精確，且需要額外執行緒。

`tqdm_class` 是 `huggingface_hub` 的官方擴展點，最穩定可靠。

### 多 tqdm 實例的進度彙總

`snapshot_download` 為每個檔案建立獨立的 tqdm 實例。`_HfProgressAdapter` 需要在所有實例間共享狀態，彙總所有檔案的下載位元組為單一進度百分比。

方案：使用一個共享的 `_SharedProgress` 物件（含 `total_bytes` 和 `downloaded_bytes`），每個 `_HfProgressAdapter` 實例持有相同引用，`update()` 時累加並計算全域百分比。

## Risks / Trade-offs

- **[風險] `tqdm_class` API 變更**：`huggingface_hub` 未來版本可能改變 tqdm 介面 → 緩解：只依賴最小 API（`__init__(total=)`, `update(n)`, `close()`），低耦合。
- **[風險] 日誌檔案寫入失敗**：磁碟滿或權限不足 → 緩解：`mkdir(parents=True, exist_ok=True)` + try/except 包裹 handler 建立，失敗時僅列印 stderr 警告，不中斷啟動。
- **[取捨] 檔案 handler 固定 DEBUG**：磁碟寫入量較大 → 可接受，5MB 上限 + 3 備份已控制總量。
