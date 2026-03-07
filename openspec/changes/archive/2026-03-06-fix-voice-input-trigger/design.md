## Context

`airtype/__main__.py` 是應用程式的入口點，負責依序建立 config、QApplication、CoreController、UI 元件，然後啟動控制器與事件迴圈。目前 `CoreController` 建立時未傳入 `HotkeyManager`，且 `SystemTrayIcon.toggle_voice_requested` Signal 未連接到控制器，導致使用者無論透過快捷鍵或系統匣選單都無法觸發語音輸入。

所有相關元件（`HotkeyManager`、`CoreController`、`SystemTrayIcon`）的內部邏輯已正確實作，問題僅在於 `main()` 函式的組裝（wiring）遺漏。

## Goals / Non-Goals

**Goals:**

- 在 `main()` 中正確建立 `HotkeyManager` 並傳入 `CoreController`
- 將 `tray.toggle_voice_requested` Signal 連接到控制器的切換邏輯
- 修復後，快捷鍵與系統匣選單均可正常觸發語音輸入

**Non-Goals:**

- 不修改 `HotkeyManager`、`CoreController`、`SystemTrayIcon` 的內部邏輯
- 不新增任何功能或 UI 變更
- 不變更快捷鍵預設值或設定結構

## Decisions

### 在 CoreController 建立前實例化 HotkeyManager

在 `main()` 中，於建立 `CoreController` 之前 `from airtype.core.hotkey import HotkeyManager` 並以 `cfg.shortcuts` 實例化，然後作為 `hotkey_manager=` 參數傳入 `CoreController()`。

**理由**：`CoreController.startup()` 已有完整的 `HotkeyManager` 整合邏輯（`on_start`/`on_stop`/`on_cancel` 回呼註冊與 `.start()` 呼叫），只需傳入實例即可啟用。

### 透過 HotkeyManager._handle_toggle 統一切換邏輯

`tray.toggle_voice_requested` Signal 連接到 `hotkey_manager._handle_toggle` 方法，而非直接呼叫 `controller._on_hotkey_start` / `_on_hotkey_stop`。

**理由**：`_handle_toggle` 已實作 INACTIVE/ACTIVE 狀態機切換，會根據當前狀態自動呼叫正確的 `on_start_cb` 或 `on_stop_cb`。直接使用此方法可避免重複實作切換邏輯，確保系統匣選單與快捷鍵行為完全一致。

**替代方案考量**：曾考慮在 `CoreController` 上新增公開的 `toggle()` 方法，但這會需要修改 controller 模組且增加複雜度。既然 `HotkeyManager._handle_toggle` 已存在且行為正確，直接連接更簡潔。

## Risks / Trade-offs

- **[Risk] `_handle_toggle` 是私有方法** → 從語意上是內部方法，但在此修復的範圍內使用合理。若未來重構 `HotkeyManager` 的介面，可在那時新增公開方法。目前保持最小變更原則。
