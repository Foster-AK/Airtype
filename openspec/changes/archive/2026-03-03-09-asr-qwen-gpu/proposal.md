## 為什麼

擁有 NVIDIA GPU 的使用者透過 PyTorch CUDA 獲得最高精度，而 AMD/Intel GPU 使用者可使用 chatllm.cpp + Vulkan。這些 GPU 路徑提供比僅 CPU 的 OpenVINO 路徑更快的推理速度與更高的準確度。

參考：PRD §6.3.2（Qwen3-ASR PyTorch CUDA 與 chatllm.cpp Vulkan 路徑）。

相依性：06-asr-abstraction、07-numpy-preprocessor。

## 變更內容

- 實作用於 CUDA 推理的 `QwenPyTorchEngine`（bfloat16）
- 實作用於 chatllm.cpp + Vulkan 推理的 `QwenVulkanEngine`（GGUF 量化）
- 兩者皆符合 ASREngine Protocol
- 在登錄檔中分別註冊為 "qwen3-pytorch-cuda" 與 "qwen3-vulkan"

## 功能

### 新增功能

- `asr-qwen-gpu`：Qwen3-ASR GPU 推理引擎（PyTorch CUDA 與 chatllm.cpp Vulkan）

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/asr_qwen_pytorch.py`、`airtype/core/asr_qwen_vulkan.py`、`tests/test_asr_qwen_gpu.py`
- 新增可選依賴：`torch`、`torchaudio`（CUDA 路徑）；chatllm.cpp 繫結（Vulkan 路徑）
- 相依：06-asr-abstraction、07-numpy-preprocessor
