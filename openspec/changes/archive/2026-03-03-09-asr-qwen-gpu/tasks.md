## 1. PyTorch CUDA 引擎

- [x] 1.1 建立 `airtype/core/asr_qwen_pytorch.py`，實作使用 qwen-asr 套件進行 bfloat16 推理的 `QwenPyTorchEngine`，符合 PyTorch CUDA — 驗證：PyTorch CUDA 推理需求
- [x] 1.2 實作可選依賴搭配優雅降級：檢查 torch + CUDA 可用性，不可用時跳過註冊 — 驗證：可選依賴搭配優雅降級需求

## 2. Vulkan 引擎

- [x] 2.1 建立 `airtype/core/asr_qwen_vulkan.py`，實作透過 subprocess 或 ctypes 繫結使用 chatllm.cpp 進行 Vulkan 推理的 `QwenVulkanEngine` — 驗證：透過 chatllm.cpp 進行 Vulkan 推理需求
- [x] 2.2 實作 chatllm.cpp 繫結的可選依賴搭配優雅降級 — 驗證：可選依賴搭配優雅降級需求

## 3. 註冊

- [x] 3.1 實作 GPU 引擎註冊："qwen3-pytorch-cuda" 與 "qwen3-vulkan" — 驗證：GPU 引擎註冊需求

## 4. 測試

- [x] 4.1 撰寫使用 mock torch/CUDA 的單元測試（測試套件缺失時的優雅降級）
- [x] 4.2 撰寫整合測試：GPU 辨識（無 GPU 可用時跳過）
