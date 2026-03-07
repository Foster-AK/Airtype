## 背景

Silero VAD v5 是一個輕量的 ONNX 模型（約 2MB），可將 32ms 音訊幀分類為語音或靜默。PRD 定義了一個 4 狀態機（IDLE → SPEECH → SILENCE_COUNTING → SPEECH_ENDED）來驅動辨識管線。

相依性：01-project-setup（設定）、02-audio-capture（音訊幀）。

## 目標 / 非目標

**目標：**

- 封裝 Silero VAD v5 ONNX 模型以進行每幀語音機率計算
- 依 PRD §6.2 實作 4 狀態 VAD 狀態機
- 從設定讀取可設定的門檻值與靜默逾時
- 在狀態轉換時發出事件

**非目標：**

- 不觸發 ASR（屬於 12-recognition-pipeline）
- 不進行音訊擷取（由 02-audio-capture 提供）
- 不進行降噪前處理

## 決策

### 透過 ONNX Runtime 使用 Silero VAD v5

以 `onnxruntime.InferenceSession` 載入 `silero_vad_v5.onnx`。模型接收 512 個 float32 樣本並回傳語音機率 [0,1]。此為 PRD §6.2 指定的同一模型。

**為何選擇 ONNX Runtime 而非 PyTorch**：依賴更輕量、啟動更快、VAD 無需 CUDA。

### 搭配事件 callback 的四狀態機

狀態：IDLE、SPEECH、SILENCE_COUNTING、SPEECH_ENDED。轉換由 `speech_prob >= threshold` 和靜默持續時間驅動。callback 透過 `on_state_change(callback)` 註冊。

**為何選擇 callback 而非 Qt Signals**：VAD 在音訊處理執行緒中運行，而非 Qt 執行緒。callback 更簡單且與執行緒無關。核心控制器（13）將橋接至 Qt Signals。

### 內建模型檔案

`silero_vad_v5.onnx` 與應用程式一同內建於 `models/vad/`。僅約 2MB，無需下載管理器。

## 風險 / 取捨

- [風險] ONNX Runtime 跨平台版本相容性 → 緩解措施：在依賴中釘選已知穩定版本
- [取捨] VAD 每幀增加約 30ms 延遲 → 依 PRD §6.2 目標可接受（<50ms）
