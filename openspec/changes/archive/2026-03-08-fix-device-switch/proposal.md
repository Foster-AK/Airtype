## Problem

在有多個音訊輸入裝置的環境下，使用者透過膠囊 UI 右鍵選單或設定視窗切換裝置後，程式不會實際切換音訊擷取串流。`config.voice.input_device` 會更新、JSON 會存檔，但 `AudioCaptureService` 繼續使用舊裝置擷取音訊，必須重啟程式才能生效。

## Root Cause

1. `overlay.py` import 了 `DeviceSelector` 但從未實例化，`CapsuleOverlay` 上不存在 `_device_selector` 屬性
2. `__main__.py:283` 的 `hasattr(overlay, "_device_selector")` 永遠為 `False`，Signal 連接從未建立
3. 膠囊 UI 的 `_on_device_selected()` 和設定視窗的 `_on_device_changed()` 都只更新 config，不呼叫 `audio_capture.set_device()`

## Proposed Solution

在 `CapsuleOverlay` 和 `SettingsVoicePage` 各新增 `device_changed = Signal(str)`，裝置選擇時 emit。在 `__main__.py` 將這兩個 Signal 連接到 `audio_capture.set_device()`。`AudioCaptureService.set_device()` 已正確實作（停止舊串流 → 更新 config → 重啟新串流），無需修改。

## Success Criteria

- 使用者從膠囊 UI 切換裝置後，音訊擷取立即使用新裝置（log 顯示切換訊息）
- 使用者從設定視窗切換裝置後，音訊擷取立即使用新裝置
- 切換後對新裝置說話，ASR 可正常辨識
- 重啟程式後自動使用上次選擇的裝置

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `overlay-ui`：膠囊裝置選單選擇後須發射 `device_changed` Signal 通知外部
- `main-wiring`：修正 Signal 連接，將膠囊和設定視窗的 `device_changed` 連接到 `audio_capture.set_device()`

## Impact

- 受影響程式碼：
  - `airtype/ui/overlay.py` — 新增 Signal 宣告與 emit
  - `airtype/ui/settings_voice.py` — 新增 Signal 宣告與 emit
  - `airtype/__main__.py` — 修正 Signal 連接邏輯
- 不需修改：`airtype/core/audio_capture.py`（`set_device()` 已正確實作）
