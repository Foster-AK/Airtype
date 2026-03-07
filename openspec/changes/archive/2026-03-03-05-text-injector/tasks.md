## 1. 核心注入

- [x] 1.1 建立 `airtype/core/text_injector.py`，實作 `TextInjector` 類別，使用 pyperclip 實作剪貼簿備份與還原策略：`_backup_clipboard()` 儲存目前內容、`_restore_clipboard()` 寫回已儲存內容 — 驗證：剪貼簿備份需求
- [x] 1.2 使用 pyperclip 加 pyautogui 實作跨平台透過貼上進行文字注入：`inject(text: str)` 方法透過 pyperclip 將文字寫入剪貼簿、透過 FocusManager 還原焦點至目標視窗、等待 50ms、然後模擬貼上 — 驗證：透過貼上進行文字注入需求
- [x] 1.3 實作可設定延遲的剪貼簿還原：貼上模擬後等待 `general.clipboard_restore_delay_ms`（預設 150ms），然後還原原始剪貼簿內容 — 驗證：剪貼簿還原需求
- [x] 1.4 實作跨平台貼上模擬：透過 `sys.platform` 偵測平台，Windows/Linux 使用 `pyautogui.hotkey('ctrl', 'v')`，macOS 使用 `pyautogui.hotkey('command', 'v')` — 驗證：跨平台貼上模擬需求
- [x] 1.5 實作貼上前焦點還原：在模擬貼上前呼叫 04-hotkey-focus 的 `FocusManager.restore_focus()`，並等待 50ms 讓焦點穩定 — 驗證：透過貼上進行文字注入需求

## 2. 依賴

- [x] 2.1 將 `pyperclip` 與 `pyautogui` 加入 `pyproject.toml` 依賴

## 3. 測試

- [x] 3.1 撰寫剪貼簿備份/還原往返的單元測試：將剪貼簿設為已知值 → 備份 → 覆寫 → 還原 → 驗證原始值 — 驗證：剪貼簿備份需求、剪貼簿還原需求
- [x] 3.2 撰寫注入時序的單元測試：mock pyautogui 與 FocusManager → 執行 inject() → 測量經過時間 < 300ms — 驗證：注入時序需求
- [x] 3.3 撰寫整合測試：注入已知文字 → 驗證其到達測試文字欄位（使用 QLineEdit 或類似的 PySide6 widget）— 驗證：透過貼上進行文字注入需求
