## Why

Airtype 目前沒有任何單一實例防護機制。每次執行 `python -m airtype` 都會建立全新的 `QApplication`，允許多個實例同時運行。這會導致嚴重的資源衝突：

- **剪貼簿注入交錯**（最危險）：多個實例的 `TextInjector.inject()` 同時操作剪貼簿，導致備份→寫入→貼上→還原流程互相干擾，使用者會貼上錯誤文字
- **音訊裝置競爭**：多個 `sounddevice.InputStream` 爭搶同一麥克風，PortAudio 可能報錯
- **全域快捷鍵重複觸發**：多個 pynput `GlobalHotKeys` 同時監聽相同按鍵組合
- **設定檔讀寫衝突**：多實例同時存取 `~/.airtype/config.json`
- **記憶體浪費**：每個實例各自載入 ASR 模型（~1-2GB/實例）
- **系統匣混亂**：出現多個系統匣圖示

## What Changes

- 在 `airtype/__main__.py` 的 `main()` 入口點新增跨平台檔案鎖機制
- 使用 Python 標準庫 `msvcrt`（Windows）/ `fcntl`（Unix），鎖檔案位於 `~/.airtype/airtype.lock`
- 第二個實例啟動時偵測到鎖已被持有，優雅退出（`sys.exit(0)`）
- 應用程式正常關閉時釋放鎖；crash 時 OS 自動釋放（flock 保證）
- 更新既有 `test_main.py` 測試以 mock 鎖函式，確保測試隔離

## Capabilities

### New Capabilities

- `single-instance-lock`: 跨平台單一實例檔案鎖機制，防止多個 Airtype 實例同時執行

### Modified Capabilities

（無）

## Impact

- 受影響程式碼：`airtype/__main__.py`（主入口點）、`tests/test_main.py`（既有測試更新）
- 新增測試：`tests/test_single_instance.py`
- 新增鎖檔案：`~/.airtype/airtype.lock`（執行時產生）
- 無新增外部依賴（使用 Python 標準庫 `msvcrt` / `fcntl`）
- 不影響其他核心元件（audio_capture、hotkey、text_injector、controller、pipeline、UI 等）
