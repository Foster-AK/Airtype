## 背景

Breeze-ASR-25 擅長臺灣華語。sherpa-onnx 為低資源系統提供最輕量的引擎。兩者皆為主要 Qwen3-ASR 之外的替代引擎。

相依性：06-asr-abstraction。

## 目標 / 非目標

**目標：**

- 透過 HuggingFace Transformers 或 faster-whisper 實作 Breeze-ASR-25 引擎
- 針對 SenseVoice 與 Paraformer 模型實作 sherpa-onnx 引擎
- 兩者皆符合 ASREngine Protocol

**非目標：**

- 不進行自訂前處理（Breeze/Whisper 有各自的；sherpa-onnx 內部處理）
- Breeze 不支援串流（Whisper 架構，僅批次；透過 VAD 分段實現偽串流）

## 決策

### Breeze-ASR-25 優先使用 faster-whisper 而非 HuggingFace pipeline

faster-whisper（CTranslate2）比 HuggingFace pipeline 顯著更快，且支援 CUDA 加速。若 faster-whisper 不可用則退回至 transformers pipeline。

### 使用 sherpa-onnx Python 繫結實作 SenseVoice 與 Paraformer

使用 `sherpa_onnx.OfflineRecognizer` 進行批次辨識，使用 `sherpa_onnx.OnlineRecognizer` 進行串流辨識。透過 `hotwords_file` 原生支援熱詞。

### 兩個引擎皆為可選依賴

若對應套件未安裝，引擎不會註冊。這保持基礎安裝的輕量性。

## 風險 / 取捨

- [風險] faster-whisper CTranslate2 可能有相容性問題 → 緩解措施：退回至 transformers pipeline
- [取捨] sherpa-onnx 串流品質可能低於 Qwen3-ASR → 作為輕量替代方案可接受
