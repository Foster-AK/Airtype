## Why

Windows WASAPI 裝置（USB 麥克風、虛擬音訊裝置等）在共享模式下不一定支援 16kHz 取樣率。目前 `AudioCaptureService` 硬編碼以 16kHz 開啟 InputStream，導致這類裝置報錯 `PaErrorCode -9997 (Invalid sample rate)`。現有 fallback 僅切換至預設裝置（仍用 16kHz），未解決根本原因。使用者選定的麥克風無法正常使用。

## What Changes

- 在 Windows 上建立 `sd.InputStream` 時加入 `extra_settings=sd.WasapiSettings(auto_convert=True)`，啟用 WASAPI `AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM` 旗標，讓 OS 驅動層自動處理取樣率轉換
- 修改涵蓋主路徑、fallback 路徑、以及設定頁面的麥克風測試功能
- 非 Windows 平台不受影響（`extra_settings` 為 `None`）
- 零 CPU 開銷：轉換在 OS 音訊引擎層完成，callback、RingBuffer、frame_queue 不需修改

## Capabilities

### New Capabilities

（無新增 capability）

### Modified Capabilities

- `audio-capture`：新增 WASAPI 平台特定設定，確保裝置在不支援 16kHz 時仍能正常開啟串流
- `settings-voice`：麥克風測試功能同步套用 WASAPI auto_convert 設定

## Impact

- 受影響程式碼：`airtype/core/audio_capture.py`、`airtype/ui/settings_voice.py`
- 受影響測試：`tests/test_audio_capture.py`
- 依賴：`sounddevice >= 0.4.7`（已滿足，pyproject.toml 已指定）
- 無新增依賴、無 API 變更、無破壞性改動
