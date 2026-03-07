## 1. Pipeline flush 機制（手動停止觸發 ASR）

- [x] 1.1 在 `airtype/core/pipeline.py` 的 BatchRecognitionPipeline 新增 `flush_and_recognize()` 方法，實作 Flush and Recognize on Manual Stop：停止累積、停止 VAD 消費、取出 buffer 送 ASR 背景執行緒；若無音訊則呼叫 `_on_recognition_cb("")`

## 2. Controller 修改（PROCESSING 超時保護）

- [x] 2.1 在 `airtype/core/controller.py` 的 CoreController `__init__` 新增 `_processing_timer` 和 `_processing_timeout_sec` 屬性
- [x] 2.2 新增 `_start_processing_timeout()`、`_cancel_processing_timeout()`、`_on_processing_timeout()` 三個方法，實作 PROCESSING State Timeout Protection（30 秒 QTimer 單次觸發 → set_error 回 IDLE）
- [x] 2.3 修改 `_on_hotkey_stop()`：轉 PROCESSING 後呼叫 `pipeline.flush_and_recognize()`（Manual Stop Triggers Pipeline Flush）；若 pipeline 為 None 直接 `cancel()` 回 IDLE；呼叫 `_start_processing_timeout()`
- [x] 2.4 修改 `on_recognition_complete()` 開頭：呼叫 `_cancel_processing_timeout()`；若 text 為空直接 transition IDLE 並 return（Empty Recognition Result Handling）
- [x] 2.5 在 `cancel()`、`set_error()`、`shutdown()` 中加入 `_cancel_processing_timeout()`（timeout cancelled on cancel）

## 3. Overlay 動畫控制（State-Driven Waveform Animation Control）

- [x] [P] 3.1 在 `airtype/ui/overlay.py` 的 `CapsuleOverlay.set_state()` 末尾加入 `self._waveform.set_active(state_name in ("LISTENING", "PROCESSING"))`，實作 state-driven waveform animation control

## 4. 主程式元件鏈建立：Application Entry Point Component Wiring（元件初始化順序與相依圖 / 容錯降級策略 / ASR 引擎登錄採用迴圈動態 import）

- [x] 4.1 Application Entry Point Component Wiring：在 `airtype/__main__.py` 新增所有必要 import（QTimer、AudioCaptureService、VadEngine、ASREngineRegistry、TextInjector、FocusManager、BatchRecognitionPipeline、DictionaryEngine、PolishEngine、set_language）
- [x] 4.2 實作 I18n Language Initialization：呼叫 `set_language(cfg.general.language)`
- [x] 4.3 建立 AudioCaptureService 並呼叫 `.start()`，以 try/except 實作容錯降級策略（Graceful Degradation on Component Failure — No Microphone Available）
- [x] 4.4 建立 VadEngine(cfg)
- [x] 4.5 實作 ASR Engine Dynamic Registration：建立 ASREngineRegistry，以迴圈動態 import 5 個引擎模組呼叫 `mod.register(registry)`，呼叫 `registry.load_default_engine(cfg)`（No ASR Model Downloaded 容錯）
- [x] 4.6 建立 FocusManager 與 TextInjector(cfg, focus_manager)
- [x] 4.7 建立 DictionaryEngine(cfg) 並呼叫 `.load_sets()`（容錯，Optional Engine Failure）
- [x] 4.8 建立 PolishEngine(cfg)（容錯，cfg.llm.enabled 時）
- [x] 4.9 建立 BatchRecognitionPipeline（需 audio_capture 和 asr_engine 非 None），傳入 on_asr_engine_used=registry.notify_used
- [x] 4.10 修改 CoreController 建立：傳入 pipeline、text_injector、polish_engine、dictionary_engine

## 5. UI 連接（RMS 輪詢採用 QTimer 而非 Qt Signal）

- [x] 5.1 建立 RMS Polling for Waveform Animation：QTimer(33ms) 輪詢 audio_capture.rms → overlay.update_rms()（僅 audio_capture 非 None 時）
- [x] 5.2 實作 Device Selector Wiring：連接 overlay._device_selector.device_changed Signal 至 audio_capture.set_device()
- [x] 5.3 實作 Settings Window Integration：傳入 dictionary_engine 至 SettingsWindow 建構子；呼叫 connect_rms_feed()（若適用）

## 6. 資源清理順序（Resource Cleanup Order）

- [x] 6.1 實作 Resource Cleanup Order：修改 `__main__.py` 關閉流程，按資源清理順序依序 rms_timer.stop() → audio_capture.stop() → asr_registry.shutdown() → controller.shutdown()

## 7. 驗證

- [x] 7.1 執行 `python -m airtype` 確認應用程式啟動無 crash，觀察 log 確認各元件初始化訊息
- [x] 7.2 驗證音波圖隨說話波動、按停止鍵不卡在 PROCESSING、Escape 取消正常
