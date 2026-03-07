## Context

`airtype/__main__.py` 是應用程式唯一入口點（`python -m airtype`）。目前僅建立 `HotkeyManager`、空殼 `CoreController`（無 pipeline/text_injector/polish/dictionary）、UI 元件（CapsuleOverlay、SettingsWindow、SystemTrayIcon），然後進入 Qt 事件迴圈。

所有核心模組的程式碼均已完成實作（changes 01–22），但 `__main__.py` 從未將它們串接起來，導致：
- 音波圖不動（RMS 資料未從 AudioCaptureService 流向 CapsuleOverlay）
- 卡在 PROCESSING（無 pipeline → `_on_hotkey_stop()` 轉狀態後無人觸發 ASR）
- 文字注入不執行（TextInjector 未建立、FocusManager 未建立）
- 裝置切換無效（DeviceSelector.device_changed 未連接）
- 辭典/LLM 功能停用（DictionaryEngine/PolishEngine 未初始化）

## Goals / Non-Goals

**Goals:**

- 在 `__main__.py` 中建立並串聯所有核心元件，使語音辨識端到端流程可運作
- 所有元件初始化均含容錯，支援優雅降級（無 ASR 模型 → 管線不建、UI 正常）
- 手動停止時能強制觸發 ASR（flush），避免卡在 PROCESSING
- PROCESSING 狀態有超時保護，30 秒無回應自動恢復 IDLE
- 音波圖正確反映即時音訊 RMS
- 關閉時按正確順序清理所有資源

**Non-Goals:**

- 不重構既有模組的內部邏輯（audio_capture、vad、asr 引擎等保持不變）
- 不處理設定變更後的即時更新（如執行時切換 ASR 引擎需重啟）
- 不新增串流辨識管線（StreamingRecognitionPipeline）的連接

## Decisions

### 元件初始化順序與相依圖

採用線性初始化順序，依相依關係排列：

```
set_language → AudioCaptureService → VadEngine → ASREngineRegistry
→ FocusManager → TextInjector → DictionaryEngine → PolishEngine
→ BatchRecognitionPipeline → HotkeyManager → CoreController → UI
```

**理由**：Pipeline 依賴前面所有元件；Controller 依賴 Pipeline 與 HotkeyManager；UI 依賴 Controller。此順序確保每個元件在被需要時已就緒。

**替代方案**：延遲初始化（lazy loading）各元件——增加首次使用延遲且複雜度較高，不適合啟動階段。

### ASR 引擎登錄採用迴圈動態 import

使用 `importlib.import_module()` 迴圈嘗試 5 個引擎模組（asr_qwen_openvino、asr_qwen_pytorch、asr_qwen_vulkan、asr_sherpa、asr_breeze），每個模組提供 `register(registry)` 函式。

**理由**：各引擎的相依套件不同（openvino、torch、chatllm 等），動態 import 讓缺少特定套件的環境仍能正常啟動。

**替代方案**：在每個引擎模組頂層 import 時自動註冊——但頂層 import 失敗會阻止整個模組載入。

### RMS 輪詢採用 QTimer 而非 Qt Signal

在 `__main__.py` 建立 33ms 間隔 QTimer，每次 timeout 讀取 `audio_capture.rms` 並呼叫 `overlay.update_rms()`。

**理由**：AudioCaptureService 的 RMS 在 PortAudio 背景執行緒計算，不適合直接 emit Qt Signal（跨執行緒 Signal 需 QObject）。QTimer 輪詢簡單且與 WaveformWidget 的動畫頻率（33ms / 30FPS）一致。

**替代方案**：讓 AudioCaptureService 繼承 QObject 並 emit Signal——侵入性修改，且 PortAudio callback 不保證與 Qt 事件迴圈相容。

### Pipeline flush 機制（手動停止觸發 ASR）

在 `BatchRecognitionPipeline` 新增 `flush_and_recognize()` 方法：停止音訊累積 → 停止 VAD 消費 → 取出 buffer → 送 ASR 背景執行緒。

**理由**：現有 pipeline 僅由 VAD SPEECH_ENDED 事件觸發 ASR，使用者手動按停止時 VAD 可能尚未偵測到靜默。需要一個 flush 入口讓 controller 強制觸發。

**替代方案**：在 `_on_hotkey_stop()` 中直接操作 pipeline 內部 buffer——違反封裝原則。

### PROCESSING 超時保護

在 `CoreController` 新增 30 秒單次 QTimer，`_on_hotkey_stop()` 轉 PROCESSING 後啟動。超時觸發 `set_error("辨識超時")` 回到 IDLE。在 `on_recognition_complete()`、`cancel()`、`set_error()`、`shutdown()` 中取消計時器。

**理由**：防止 ASR 引擎卡死或網路 API 無回應時使用者永遠停留在 PROCESSING。30 秒足以涵蓋大多數離線辨識場景。

**替代方案**：不加超時，依靠使用者按 Escape 取消——使用者可能不知道可以取消。

### 容錯降級策略

| 元件 | 失敗時行為 |
|------|-----------|
| AudioCaptureService | `audio_capture = None` → pipeline 不建 → UI 正常但無辨識 |
| ASR 引擎 | `asr_engine = None` → pipeline 不建 → 同上 |
| VAD 模型 | VadEngine 延遲載入 → pipeline error callback → controller.set_error() |
| DictionaryEngine | `dictionary_engine = None` → controller 跳過辭典處理 |
| PolishEngine | `polish_engine = None` → controller 跳過 LLM 潤飾 |
| 無 pipeline 按停止 | `_on_hotkey_stop()` 直接 `cancel()` 回 IDLE |

### 資源清理順序

關閉時反向清理：`rms_timer.stop()` → `audio_capture.stop()` → `asr_registry.shutdown()` → `controller.shutdown()`

**理由**：先停 RMS 輪詢（避免存取已停止的 audio_capture），再停音訊擷取，再卸載 ASR 模型，最後關閉 controller（停止 pipeline 與 hotkey）。

## Risks / Trade-offs

- [Risk] ASR 引擎全部無法載入（模型均未下載） → Mitigation：pipeline 不建立，UI 正常顯示，使用者可在設定頁下載模型後重啟
- [Risk] flush_and_recognize 與 VAD SPEECH_ENDED 同時觸發產生競態 → Mitigation：flush 先設 `_accumulating = False` 並停止 VAD 消費，確保不會重複處理
- [Risk] QTimer 在 Qt 事件迴圈繁忙時 RMS 輪詢延遲 → Mitigation：33ms 間隔已足夠寬鬆，偶爾跳幀對動畫視覺影響極小
- [Risk] 元件初始化失敗時 log 可能不夠明確 → Mitigation：每個 try/except 區塊均記錄具體錯誤訊息與建議操作
