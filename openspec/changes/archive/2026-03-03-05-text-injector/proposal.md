## 為什麼

ASR 產出文字後，必須將其注入使用者的作用中應用程式的游標位置。基於剪貼簿的注入方式（備份剪貼簿 → 寫入文字 → 模擬 Ctrl+V → 還原剪貼簿）是最可靠的跨平台方法。此變更為辨識管線（12）的前置需求。

參考：PRD §6.5（文字注入引擎）、§7.2（跨平台輸入模擬）。

相依性：01-project-setup、04-hotkey-focus（焦點管理）。

## 變更內容

- 使用 pyperclip 與 pyautogui 在 `airtype/core/text_injector.py` 中實作 `TextInjector`
- 實作文字注入前後的剪貼簿備份與還原
- 寫入文字至剪貼簿後模擬貼上按鍵（Windows/Linux 為 Ctrl+V，macOS 為 Cmd+V）
- 整合 04-hotkey-focus 的 FocusManager，在貼上前還原焦點至目標視窗
- 加入貼上後剪貼簿還原的可設定延遲（預設 150ms）

## 功能

### 新增功能

- `text-injection`：基於剪貼簿的文字注入至任何應用程式，包含剪貼簿備份/還原

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/text_injector.py`、`tests/test_injector.py`
- 新增依賴：`pyperclip`、`pyautogui`
- 相依：01-project-setup（設定、日誌記錄）、04-hotkey-focus（FocusManager 用於焦點還原）
