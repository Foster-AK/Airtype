## Problem

`__main__.py` 啟動流程中有兩個關鍵遺漏，導致語音輸入功能完全無法觸發：

1. **未建立 `HotkeyManager`**：`CoreController` 初始化時 `hotkey_manager=None`，`startup()` 中的 `if self._hotkey_manager is not None:` 判斷永遠跳過，全域快捷鍵監聽器從未啟動。
2. **`tray.toggle_voice_requested` 未連接**：系統匣選單的「切換語音輸入」動作觸發 `toggle_voice_requested` Signal，但該 Signal 未連接到任何 handler，點擊後無效果。

## Root Cause

`airtype/__main__.py` 的 `main()` 函式在建立 `CoreController` 時只傳入 `config=cfg`，未實例化 `HotkeyManager(cfg.shortcuts)` 並傳入 `hotkey_manager` 參數。此外，`tray.toggle_voice_requested` Signal 在 `SystemTrayIcon` 中已定義並連接至選單動作，但 `main()` 中未將其連接到控制器的狀態切換邏輯。

## Proposed Solution

修改 `airtype/__main__.py`：

1. 在建立 `CoreController` 之前，匯入 `HotkeyManager` 並以 `cfg.shortcuts` 建立實例，傳入 `CoreController(config=cfg, hotkey_manager=hotkey_manager)`。
2. 在建立 `SystemTrayIcon` 後，將 `tray.toggle_voice_requested` 連接至控制器的切換邏輯（在 IDLE 時呼叫 `_on_hotkey_start`，在 LISTENING 時呼叫 `_on_hotkey_stop`）。

## Success Criteria

- 按下 `ctrl+shift+space`（預設快捷鍵）時，應用程式狀態從 IDLE 轉換為 ACTIVATING → LISTENING。
- 再次按下 `ctrl+shift+space` 時，從 LISTENING 轉換為 PROCESSING。
- 點擊系統匣選單「切換語音輸入」時，行為與快捷鍵相同。
- 按下 Escape 時，從任何活躍狀態取消回到 IDLE。

## Impact

- 受影響程式碼：`airtype/__main__.py`（主要修改點）
- 相關模組（不需修改，僅參考）：`airtype/core/hotkey.py`、`airtype/core/controller.py`、`airtype/ui/tray_icon.py`
