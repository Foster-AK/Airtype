## 1. 修復 Application Bootstrap Wiring — 在 CoreController 建立前實例化 HotkeyManager

- [x] 1.1 修復 Application Bootstrap Wiring：在 `airtype/__main__.py` 中匯入 `HotkeyManager`，以 `cfg.shortcuts` 建立實例，並傳入 `CoreController(config=cfg, hotkey_manager=hotkey_manager)`

## 2. 修復 Application Bootstrap Wiring — 透過 HotkeyManager._handle_toggle 統一切換邏輯

- [x] 2.1 完成 Application Bootstrap Wiring：在 `airtype/__main__.py` 中將 `tray.toggle_voice_requested` Signal 連接至 `hotkey_manager._handle_toggle`，使系統匣選單觸發與快捷鍵相同的狀態切換

## 3. 測試驗證

- [x] [P] 3.1 撰寫測試驗證 Application Bootstrap Wiring 中 `HotkeyManager` 被正確建立並傳入 `CoreController`
- [x] [P] 3.2 撰寫測試驗證 Application Bootstrap Wiring 中 `tray.toggle_voice_requested` Signal 觸發時呼叫 `hotkey_manager._handle_toggle`
