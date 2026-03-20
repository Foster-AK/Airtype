## Why

Airtype 目前在 macOS Apple Silicon 上沒有可用的 Qwen3-ASR 推理路徑。OpenVINO 不支援 ARM Mac、PyTorch CUDA 需要 NVIDIA GPU、chatllm.cpp Vulkan 在 macOS 上缺乏穩定支援。這導致 MacBook Air M1 等裝置上麥克風正常啟動但 ASR 引擎全部載入失敗，整條辨識管線無法運作。

開源專案 [mlx-qwen3-asr](https://github.com/moona3k/mlx-qwen3-asr/)（Apache 2.0 授權）提供了 Qwen3-ASR 的完整 MLX 原生實作，專為 Apple Silicon 最佳化。0.6B 模型在 M 系列晶片上延遲僅 0.11–0.46 秒，WER 2.29%（LibriSpeech），完全滿足即時語音輸入需求。

## What Changes

- 新增 `airtype/core/asr_qwen_mlx.py` 引擎模組，封裝 `mlx-qwen3-asr` 的 `Session` API
- 引擎 ID 為 `qwen3-mlx`，遵循 `ASREngine` Protocol（batch recognize、context text、延遲載入）
- 模型格式為 HuggingFace safetensors（MLX 格式），透過 `huggingface-hub` 下載至 `~/.airtype/models/`
- 在 `__main__.py` 的 `_ENGINE_MODULE_MAP` 新增 MLX 模組路徑
- 在 `_MODEL_ENGINE_MAP` 的 `qwen3-asr-0.6b` 候選清單加入 `qwen3-mlx`
- 硬體偵測新增 Apple Silicon 判斷，自動推薦 MLX 推理路徑
- `models/manifest.json` 新增 MLX 模型條目
- macOS 打包配置新增 `mlx` 可選依賴

## Capabilities

### New Capabilities

- `asr-qwen-mlx`: Qwen3-ASR MLX 推理引擎，專屬 macOS Apple Silicon 的語音辨識後端。包含模型載入、Mel 特徵提取、自回歸解碼、引擎登錄與延遲載入。

### Modified Capabilities

- `hardware-detection`: 新增 Apple Silicon 晶片偵測與 MLX 推理路徑推薦邏輯
- `asr-abstraction`: `_MODEL_ENGINE_MAP` 新增 `qwen3-mlx` 候選引擎
- `main-wiring`: `_ENGINE_MODULE_MAP` 新增 `airtype.core.asr_qwen_mlx` 模組路徑

## Impact

- 新增檔案：`airtype/core/asr_qwen_mlx.py`、`tests/test_asr_qwen_mlx.py`
- 修改檔案：`airtype/__main__.py`、`airtype/core/asr_engine.py`、`airtype/utils/hardware.py`、`models/manifest.json`
- 新增依賴：`mlx>=0.18.0`、`mlx-qwen3-asr`（僅 macOS，條件安裝）
- 平台限制：`mlx` 套件僅支援 macOS Apple Silicon，Windows/Linux 上此引擎不會被登錄
