## 為什麼

Breeze-ASR-25 提供最佳的臺灣華語 + 語碼轉換準確度，而 sherpa-onnx（SenseVoice/Paraformer）則為低資源裝置提供最輕量的選項。這些與主要的 Qwen3-ASR 引擎互補。

參考：PRD §6.3.3（Breeze-ASR-25）、§6.3.4（sherpa-onnx 整合）。

相依性：06-asr-abstraction。

## 變更內容

- 使用 HuggingFace Transformers pipeline 或 faster-whisper 實作 `BreezeAsrEngine`
- 使用 sherpa-onnx Python 繫結（SenseVoice、Paraformer）實作 `SherpaOnnxEngine`
- 兩者皆符合 ASREngine Protocol
- 在登錄檔中分別註冊為 "breeze-asr-25" 與 "sherpa-sensevoice" / "sherpa-paraformer"

## 功能

### 新增功能

- `asr-breeze`：Breeze-ASR-25 引擎，針對臺灣華語與語碼轉換最佳化辨識
- `asr-sherpa`：sherpa-onnx 引擎，用於輕量的 SenseVoice 與 Paraformer 模型

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/asr_breeze.py`、`airtype/core/asr_sherpa.py`、`tests/test_asr_alternatives.py`
- 新增可選依賴：`transformers` 或 `faster-whisper`（Breeze）；`sherpa-onnx`（SenseVoice/Paraformer）
- 相依：06-asr-abstraction
