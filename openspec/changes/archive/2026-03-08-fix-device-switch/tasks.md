## 1. CapsuleOverlay Signal 修復

- [x] [P] 1.1 在 CapsuleOverlay 新增 device_changed Signal — 在 `airtype/ui/overlay.py` 的 `PySide6.QtCore` import 區塊加入 `Signal`，並在 `CapsuleOverlay` class 宣告 `device_changed = Signal(str)`。在 `_on_device_selected()` 末尾加入 `self.device_changed.emit(device_name)`，實作 Device Dropdown Button 需求。**驗證**：`CapsuleOverlay` 實例具有 `device_changed` 屬性，呼叫 `_on_device_selected("test")` 後 Signal 被 emit。

## 2. SettingsVoicePage Signal 修復

- [x] [P] 2.1 在 SettingsVoicePage 新增 device_changed Signal — 在 `airtype/ui/settings_voice.py` 的 `SettingsVoicePage` class 宣告 `device_changed = Signal(str)`（`Signal` 已在第 35 行 import）。修改 `_on_device_changed()` 將 `currentData()` 提取為變數並在末尾 emit `self.device_changed.emit(device_name)`。**驗證**：`SettingsVoicePage` 實例具有 `device_changed` 屬性。

## 3. Device Selector Wiring 修正

- [x] 3.1 修正 __main__.py Signal 連接 — 將第 282-284 行的失效 `hasattr(overlay, "_device_selector")` 條件替換為直接連接 `overlay.device_changed` 和 `settings_window._page_voice.device_changed` 到 `audio_capture.set_device()`，實作 Device Selector Wiring 需求。**驗證**：啟動程式後，log 中不再出現 `_device_selector` 相關警告；從膠囊 UI 和設定視窗分別切換裝置後，log 顯示「已切換至裝置」訊息。

## 4. 測試驗證

- [x] 4.1 更新 `tests/test_overlay.py` — 新增測試案例驗證 `CapsuleOverlay.device_changed` Signal 在 `_on_device_selected()` 呼叫後被正確 emit，且 emit 的值為裝置名稱字串。**驗證**：`pytest tests/test_overlay.py -v` 通過。

- [x] 4.2 端對端手動測試 — 連接 2+ 麥克風，啟動程式，從膠囊右鍵選單切換裝置→log 顯示切換；從設定視窗切換裝置→log 顯示切換；對新裝置說話→ASR 正常辨識。**驗證**：所有切換路徑均正常運作。
