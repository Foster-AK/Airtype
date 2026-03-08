## Why

當 Windows 系統中同一隻麥克風跨多個 Host API（MME、DirectSound、WASAPI、WDM-KS）出現同名裝置時，Airtype 使用裝置名稱（字串）傳給 `sd.InputStream(device=...)`，導致 sounddevice 的 `_get_device_id()` 找到多個匹配後拋出 `ValueError: Multiple input devices found`，音訊串流無法啟動。

## What Changes

- 將裝置選擇鏈路從**裝置名稱（str）**改為**裝置 index（int）**：UI 下拉選單的 itemData、config 儲存值、audio_capture 開串流參數全部統一使用 sounddevice 裝置 index
- Config 的 `VoiceConfig.input_device` 型別從 `str` 擴展為 `str | int`（保留 `"default"` 字串作為系統預設）
- 新增 fallback 機制：若儲存的 index 對應裝置已不存在（拔插/重啟），自動退回系統預設裝置

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `audio-capture`：裝置選擇參數型別從字串改為整數 index
- `settings-voice`：UI 裝置選擇下拉選單的 itemData 改存裝置 index；Signal 型別調整
- `config-management`：`VoiceConfig.input_device` 欄位型別擴展為 `str | int`

## Impact

- 受影響程式碼：
  - `airtype/config.py`（VoiceConfig dataclass）
  - `airtype/ui/device_selector.py`（DeviceSelector 元件 + list_input_devices）
  - `airtype/ui/settings_voice.py`（VoiceSettingsPage 裝置選擇與麥克風測試）
  - `airtype/core/audio_capture.py`（AudioCaptureService.start fallback）
- 受影響設定檔：`~/.airtype/config.json`（`voice.input_device` 值可能從字串變為整數）
