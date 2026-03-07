## 背景

GPU 使用者獲得更快且更準確的推理。兩條路徑：PyTorch CUDA（NVIDIA）與 chatllm.cpp + Vulkan（任何 GPU）。

相依性：06-asr-abstraction、07-numpy-preprocessor。

## 目標 / 非目標

**目標：**

- NVIDIA GPU 的 PyTorch CUDA 引擎（bfloat16 推理）
- AMD/Intel GPU 的 chatllm.cpp Vulkan 引擎（GGUF 量化）
- 兩者皆支援批次與潛在的串流推理

**非目標：**

- 這些引擎不進行 CPU 退回（屬於 08-asr-qwen-openvino）
- 不進行模型下載（屬於 11-model-hardware-mgr）

## 決策

### PyTorch CUDA 搭配 qwen-asr 套件

使用 `qwen-asr` Python 套件或直接 transformers 整合進行 CUDA 推理。bfloat16 精度以獲得最佳準確度。

### chatllm.cpp 透過 subprocess 或 ctypes 繫結

chatllm.cpp 提供帶有 Vulkan 後端的 C++ 推理執行時。透過 subprocess（最簡單）或 ctypes/cffi 繫結介接。GGUF 模型格式。

### 可選依賴搭配優雅降級

`torch` 與 chatllm.cpp 皆為可選。若未安裝，引擎僅不在 ASREngineRegistry 中註冊。

## 風險 / 取捨

- [風險] PyTorch 是約 2GB 的依賴 → 緩解措施：可選，僅在使用者有 NVIDIA GPU 時安裝
- [風險] chatllm.cpp Vulkan 支援在不同 GPU 廠商間有差異 → 緩解措施：硬體偵測在推薦前驗證 Vulkan 支援
- [取捨] 兩個獨立的引擎實作 → 必要的，因為 CUDA 與 Vulkan 有根本不同的執行時需求
