## Context

Airtype 桌面應用程式（`airtype/__main__.py:main()`）目前允許多個實例同時執行。每次執行都建立全新的 `QApplication`，沒有任何單一實例檢查機制。多實例會導致剪貼簿注入交錯、音訊裝置競爭、快捷鍵重複觸發等嚴重問題。

現有的 `main()` 啟動順序：`setup_logging` → `AirtypeConfig.load()` → `QApplication()` → 元件初始化 → `app.exec()` → 資源清理 → `sys.exit()`。

## Goals / Non-Goals

**Goals:**

- 防止多個 Airtype 實例同時執行
- 第二個實例啟動時優雅退出（日誌警告 + `sys.exit(0)`）
- crash 後鎖自動釋放，不阻擋下次啟動
- 跨平台支援（Windows / macOS / Linux）
- 不影響既有元件的初始化順序與行為
- 不影響既有測試（透過 mock 隔離）

**Non-Goals:**

- 不實作「喚醒既有實例」功能（IPC 通知既有實例彈出視窗）
- 不新增設定項（如 `single_instance_enabled`），此為必要行為
- 不修改任何核心元件（audio_capture、hotkey、text_injector、controller 等）

## Decisions

### 檔案鎖機制（File Lock）

**選擇**：使用 OS 層級的檔案鎖（`fcntl.flock` / `msvcrt.locking`）
**替代方案**：
- TCP Socket（`127.0.0.1:<port>`）：被企業防火牆阻擋風險高、可能與其他軟體 port 衝突、subprocess 可能繼承 FD
- Windows Named Mutex（`ctypes.windll.kernel32.CreateMutexW`）：不跨平台
- PID 檔案（寫入 PID + 檢查進程存活）：crash 後殘留需要額外清理邏輯，存在 TOCTOU 競態條件

**理由**：檔案鎖是唯一同時滿足以下條件的方案：
1. 跨平台（Windows / macOS / Linux）
2. crash 時 OS 自動釋放（flock 保證）
3. 無防火牆風險
4. 無 port 衝突
5. 使用 Python 標準庫，無額外依賴

### 鎖檔案位置

**選擇**：`~/.airtype/airtype.lock`
**理由**：與 `config.json` 和 `logs/` 相同目錄層級，保持一致性。鎖函式需自行 `os.makedirs(~/.airtype, exist_ok=True)`，因為鎖的取得在 `AirtypeConfig.load()` 之前。

### 鎖的取得時機

**選擇**：在 `main()` 中 `setup_logging("INFO")` 之後、`AirtypeConfig.load()` 之前
**理由**：需要 logger 來記錄鎖失敗的警告訊息，但必須在 `QApplication` 建立前就阻止第二個實例。

### 鎖失敗時的行為

**選擇**：`logger.warning()` + `sys.exit(0)`（正常退出碼）
**替代方案**：
- `sys.exit(1)`：語義上非錯誤，只是「已有實例在執行」
- 彈出 Qt 對話框提示：需要先建立 `QApplication`，與鎖的目的矛盾
- 優雅降級（繼續啟動）：違反單一實例的設計目的

### 測試策略

**選擇**：提取獨立函式 `_acquire_instance_lock()` 並在 `test_main.py` 中 patch
**理由**：
- 既有 7 個測試都透過 `with patch(...)` mock 所有依賴來呼叫 `main()`
- 新增一行 `patch("airtype.__main__._acquire_instance_lock", return_value=MagicMock())` 即可
- 獨立測試檔案 `test_single_instance.py` 使用真實 `tempfile` 測試鎖邏輯

## Risks / Trade-offs

- **[風險] NFS / 網路檔案系統上 flock 不可靠** → `~/.airtype/` 一定在本機磁碟，不受影響
- **[風險] Windows 上 `msvcrt.locking` 行為差異** → 只鎖 1 byte，Windows 與 Unix 語義一致
- **[風險] 測試遺漏 patch** → 測試仍能通過（因為是第一個實例），但會留下殘留 lock 檔案。以 code review 把關
- **[取捨] 不提供「喚醒既有實例」** → 簡化實作，未來可透過 IPC 擴展
