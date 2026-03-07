## Why

`__main__.py` 目前僅建立 HotkeyManager 與空殼 CoreController，所有核心元件（AudioCaptureService、VadEngine、ASREngineRegistry、BatchRecognitionPipeline、TextInjector、FocusManager、DictionaryEngine、PolishEngine）均未初始化，導致語音辨識流程完全無法運作——音波圖不動、按停止後卡在「處理中」無法恢復、文字注入不執行。此外 UI 層的 RMS 輪詢、裝置切換 Signal、i18n 語言設定、辭典設定頁連接等也全部缺失。

## What Changes

- 在 `__main__.py` 中建立完整元件鏈：AudioCaptureService → VadEngine → ASREngineRegistry（登錄 5 個引擎） → BatchRecognitionPipeline → FocusManager + TextInjector → DictionaryEngine → PolishEngine → CoreController（傳入所有元件）
- 新增 RMS 輪詢 QTimer（33ms）驅動膠囊音波圖動畫
- 連接 DeviceSelector.device_changed Signal 至 AudioCaptureService.set_device()
- 呼叫 `set_language(cfg.general.language)` 初始化 i18n
- 傳入 dictionary_engine 至 SettingsWindow 並呼叫 connect_rms_feed()
- 在 `BatchRecognitionPipeline` 新增 `flush_and_recognize()` 方法，供手動停止時強制觸發 ASR
- 修改 `CoreController._on_hotkey_stop()` 呼叫 pipeline flush 並啟動 PROCESSING 超時（30 秒 QTimer）
- 在 `CapsuleOverlay.set_state()` 中根據狀態啟停 WaveformWidget 動畫
- 所有元件初始化均含容錯（try/except），支援優雅降級

## Capabilities

### New Capabilities

- `main-wiring`: 應用程式入口點的完整元件初始化與連接，包含元件建立順序、容錯降級策略、RMS 輪詢、裝置切換連接、清理順序

### Modified Capabilities

- `core-controller`: 新增 PROCESSING 超時機制（30 秒 QTimer → set_error 回 IDLE）；_on_hotkey_stop() 呼叫 pipeline.flush_and_recognize()
- `recognition-pipeline`: BatchRecognitionPipeline 新增 flush_and_recognize() 方法，強制取出累積音訊並觸發 ASR
- `overlay-ui`: CapsuleOverlay.set_state() 依狀態啟停 WaveformWidget 動畫（set_active）

## Impact

- 受影響程式碼：
  - `airtype/__main__.py`（核心重寫：建立完整元件鏈）
  - `airtype/core/pipeline.py`（新增 flush_and_recognize 方法）
  - `airtype/core/controller.py`（修改 _on_hotkey_stop + 新增超時機制）
  - `airtype/ui/overlay.py`（set_state 啟停動畫）
- 受影響相依：所有已實作的核心模組（audio_capture、vad、asr_engine、text_injector、hotkey、dictionary、llm_polish、i18n）
- 無 API 或依賴套件變更
