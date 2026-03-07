## 背景

QwenASRMiniTool 已在 Windows 上驗證 OpenVINO INT8 路徑。0.6B 模型的峰值 RAM 約 4.8GB。這是預設的「開箱即用」引擎。

相依性：06-asr-abstraction、07-numpy-preprocessor。

## 目標 / 非目標

**目標：**

- 載入 Qwen3-ASR INT8 OpenVINO IR 模型
- 在 CPU 上執行批次推理
- 透過提示建構支援上下文偏移

**非目標：**

- 不進行串流推理（OpenVINO 路徑僅支援批次）
- 不進行 GPU 加速（屬於 09-asr-qwen-gpu）

## 決策

### 透過 openvino.Core 載入 OpenVINO IR 模型

使用 `openvino.Core().compile_model()` 載入 INT8 量化模型。輸入：來自 07-numpy-preprocessor 的預處理 Mel 特徵。輸出：token ID 解碼為文字。

### 透過提示 token 注入實現上下文偏移

將熱詞作為 BPE 提示 token 的一部分注入。前處理器以前置上下文文字的方式建構提示模板，遵循 QwenASRMiniTool 的方法。

### 延遲載入模型

模型在首次使用時載入，而非應用程式啟動時。這保持啟動速度快（目標 <3s）。

## 風險 / 取捨

- [風險] 峰值 RAM 約 4.8GB 對 6GB 系統可能過高 → 緩解措施：透過硬體偵測建議 SenseVoice 作為退回方案
- [取捨] 僅批次（無串流）→ 可接受；串流使用 Qwen3-ASR GPU 路徑或 VAD 分段偽串流
