## Context

Airtype 在 macOS Apple Silicon（M1/M2/M3/M4）上缺乏可用的 Qwen3-ASR 推理路徑。現有三條 Qwen3-ASR 路徑（OpenVINO INT8、PyTorch CUDA、chatllm.cpp Vulkan）均不支援 ARM macOS，導致 macOS 使用者的辨識管線無法啟動。

開源專案 `mlx-qwen3-asr`（Apache 2.0）提供完整的 MLX 原生 Qwen3-ASR 實作，包含自行實作的 Mel 特徵提取、BPE tokenizer、encoder-decoder 推理、Session API。0.6B 模型在 M 系列晶片上 8-bit 量化延遲僅 0.11s（M4 Pro），記憶體需求約 1.2GB。

## Goals / Non-Goals

**Goals:**

- 新增 `MLXQwen3ASREngine` 引擎，完全遵循現有 `ASREngine` Protocol
- 封裝 `mlx-qwen3-asr` 的 `Session` API，支援批次辨識（batch recognize）
- 支援延遲載入（prepare → 首次 recognize 時自動 load）
- 支援 context text 注入（領域詞彙偏向）
- 在硬體偵測中新增 Apple Silicon 判斷，自動推薦 MLX 路徑
- `mlx` 為條件依賴，僅 macOS 時安裝；非 macOS 平台此引擎不會被登錄

**Non-Goals:**

- 不實作串流辨識（`mlx-qwen3-asr` 的 streaming 為實驗性，初期使用 VAD 分段 + 批次模式）
- 不支援 1.7B 模型（初期僅 0.6B，可後續擴充）
- 不修改 `mlx-qwen3-asr` 套件本身（作為外部依賴使用）
- 不處理 macOS 麥克風權限提示（這是 OS 層級，由使用者手動授權）

## Decisions

### MLX Session API 封裝策略

使用 `mlx_qwen3_asr.Session` 類別作為引擎核心。`Session` 提供顯式的 model + tokenizer 生命週期管理，支援 `transcribe()` 接收 `(np.ndarray, sample_rate)` tuple。

替代方案：直接使用 `transcribe()` 全域函式 — 但全域函式使用模組級 singleton cache，不利於引擎的 `unload()` 控制。

### 模型格式與下載機制

使用 HuggingFace safetensors 格式，透過 `huggingface-hub` 的 `snapshot_download()` 下載至 `~/.airtype/models/qwen3-asr-0.6b-mlx/`。預設模型 ID 為 `Qwen/Qwen3-ASR-0.6B`。

替代方案：預先轉換為自有格式 — 增加維護成本且 `mlx-qwen3-asr` 已處理權重映射。

### 引擎 ID 與登錄位置

引擎 ID 為 `qwen3-mlx`，在 `_MODEL_ENGINE_MAP["qwen3-asr-0.6b"]` 候選清單末尾加入（優先級低於 openvino/cuda/vulkan，因為這些在非 macOS 平台更成熟）。在 macOS Apple Silicon 上由於其他引擎不可用，`auto` 策略自然會選到 `qwen3-mlx`。

### 音訊前處理路徑

`mlx-qwen3-asr` 內建完整的 Mel 特徵提取（STFT + Mel filterbank + Whisper 風格正規化），接受 `np.ndarray` 16kHz mono PCM float32。不需要使用 Airtype 的 `NumpyPreprocessor`，直接傳入 raw audio。

### 條件安裝策略

`pyproject.toml` 新增 `[project.optional-dependencies]` 的 `mlx` extra：
```
mlx = ["mlx>=0.18.0", "mlx-qwen3-asr>=0.1.0"]
```
macOS 打包時包含此 extra；Windows/Linux 不安裝。`register()` 函式嘗試 `import mlx` 失敗時靜默跳過。

### Apple Silicon 硬體偵測

在 `HardwareDetector` 中新增 `is_apple_silicon` 偵測（`platform.machine() == "arm64"` + `sys.platform == "darwin"`）。推薦決策樹新增分支：Apple Silicon → engine=`qwen3-mlx`, model=`qwen3-asr-0.6b`。

## Risks / Trade-offs

- **[Risk] mlx-qwen3-asr API 不穩定** → Mitigation：鎖定最低版本 `>=0.1.0`，在 `Session` 封裝層處理例外，必要時可 pin 特定版本。
- **[Risk] 模型下載需要網路** → Mitigation：與現有 model-download 機制一致，首次使用時提示下載。
- **[Risk] M1 記憶體壓力（8GB 機型）** → Mitigation：0.6B 模型僅 ~1.2GB，且引擎支援閒置 5 分鐘自動卸載。
- **[Trade-off] 不支援串流辨識** → 初期使用 VAD 分段 + 批次模式已可滿足即時輸入需求（單段 <15 秒音訊推理 <0.5 秒）。
- **[Trade-off] 僅限 macOS Apple Silicon** → 這是 MLX 框架本身的限制，其他平台繼續使用現有推理路徑。
