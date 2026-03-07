## 1. 快捷鍵監聽器

- [x] 1.1 建立 `airtype/core/hotkey.py`，於 daemon thread 中使用 pynput 監聽器（依設計於 daemon thread 中執行 pynput 監聽器）：實作 `HotkeyManager` 類別，包含 `start()` / `stop()` 生命週期、於 daemon thread 中執行的 pynput `Listener`，以及透過 `on_start`、`on_stop`、`on_cancel` 註冊 callback — 驗證：快捷鍵註冊需求、跨平台快捷鍵支援需求
- [x] 1.2 實作從設定註冊快捷鍵（依設計從設定註冊快捷鍵）：將按鍵組合字串（例如 `"ctrl+shift+space"`）解析為 pynput key sets，從設定 shortcuts 區段讀取 `toggle_voice` 快捷鍵，支援修飾鍵+按鍵組合（ctrl、shift、alt、cmd/super）— 驗證：快捷鍵註冊需求（註冊預設快捷鍵情境、自訂快捷鍵情境）
- [x] 1.3 實作快捷鍵切換行為與取消快捷鍵（依設計於快捷鍵模組中實作切換狀態機）：維護 INACTIVE/ACTIVE 切換狀態，第一次按下觸發 start callback，第二次按下觸發 stop callback，Escape 鍵觸發 cancel callback 並重設為 INACTIVE — 驗證：快捷鍵切換行為需求、取消快捷鍵需求

## 2. 焦點管理

- [x] 2.1 建立 `airtype/utils/platform_utils.py`，包含 FocusManager 抽象介面（依設計實作平台特定焦點管理）：定義 `FocusManager` 抽象基底類別，包含 `record()` 與 `restore()` 方法，實作工廠函式 `create_focus_manager()`，根據 `sys.platform` 回傳正確的平台特定實作 — 驗證：FocusManager 介面需求
- [x] 2.2 實作 Windows 焦點管理：`WindowsFocusManager` 使用 `ctypes.windll.user32` — 以 `GetForegroundWindow` 記錄、以 `SetForegroundWindow` 搭配 `AttachThreadInput` 可靠地還原焦點 — 驗證：跨平台焦點操作需求（Windows 焦點管理情境）、記錄作用中視窗需求、還原焦點需求
- [x] 2.3 實作 macOS 焦點管理：`MacOSFocusManager` 使用 `subprocess.run(["osascript", ...])` — 查詢最前方應用程式名稱進行記錄、依名稱啟動應用程式進行還原 — 驗證：跨平台焦點操作需求（macOS 焦點管理情境）
- [x] 2.4 實作 Linux 焦點管理：`LinuxFocusManager` 使用 `subprocess.run(["xdotool", ...])` — 以 `getactivewindow` 記錄、以 `windowactivate` 還原 — 驗證：跨平台焦點操作需求（Linux 焦點管理情境）
- [x] 2.5 實作跨平台快捷鍵支援檢查：macOS 輔助使用權限偵測，包含錯誤記錄與使用者指示；Linux Wayland 偵測，包含警告記錄 — 驗證：跨平台快捷鍵支援需求（macOS 未授予輔助使用權限情境、Linux Wayland 偵測情境）、還原焦點需求（目標視窗已關閉情境）

## 3. 依賴

- [x] 3.1 將 `pynput` 加入 `pyproject.toml` 依賴

## 4. 測試

- [x] 4.1 撰寫快捷鍵按鍵組合解析的單元測試：驗證 `"ctrl+shift+space"`、`"ctrl+alt+r"`、`"alt+f1"` 與無效組合的解析 — 驗證：快捷鍵註冊需求
- [x] 4.2 撰寫 FocusManager 的單元測試（mock 平台呼叫）：驗證 `record()` 儲存視窗資訊、`restore()` 呼叫平台 API、工廠依平台回傳正確實作 — 驗證：FocusManager 介面需求、記錄作用中視窗需求、還原焦點需求
- [x] 4.3 撰寫整合測試：註冊快捷鍵 → 模擬按鍵 → 驗證 callback 觸發，驗證切換狀態轉換（start/stop/cancel）— 驗證：快捷鍵切換行為需求、取消快捷鍵需求
