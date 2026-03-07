## 為什麼

Qwen3-ASR 搭配 OpenVINO INT8 量化是 Airtype 的主要（預設）ASR 引擎——它在 CPU 上執行無需 GPU，使其成為通用的「到處都能用」路徑。基於 QwenASRMiniTool 已驗證的實作。

參考：PRD §6.3.2（Qwen3-ASR 整合）、§6.3.5（OpenVINO INT8 路徑）。

相依性：06-asr-abstraction、07-numpy-preprocessor。

## 變更內容

- 實作符合 ASREngine Protocol 的 `QwenOpenVinoEngine`
- 透過 openvino runtime 載入 Qwen3-ASR-0.6B/1.7B INT8 OpenVINO IR 模型
- 使用 NumPy 前處理器進行 Mel 頻譜 + BPE 分詞
- 支援上下文偏移（透過系統提示注入熱詞）
- 在 ASR 引擎登錄檔中註冊為 "qwen3-openvino"

## 功能

### 新增功能

- `asr-qwen-openvino`：Qwen3-ASR OpenVINO INT8 引擎，用於 CPU 語音辨識

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/asr_qwen_openvino.py`、`tests/test_asr_qwen_openvino.py`
- 新增依賴：`openvino`（OpenVINO 工具組）
- 模型檔案：`models/asr/qwen3_asr_int8/`（約 1.2GB，按需下載）
- 相依：06-asr-abstraction、07-numpy-preprocessor
