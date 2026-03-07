## 為什麼

使用者不應需要手動選擇 ASR 引擎或下載模型。硬體偵測自動選擇最佳推理路徑，而模型管理器處理下載、完整性驗證與進度回報。

參考：PRD §10.4（硬體自動偵測）、§6.3.7（模型下載與管理）。

相依性：06-asr-abstraction。

## 變更內容

- 在 `airtype/utils/hardware_detect.py` 中實作 `HardwareDetector` 以偵測 GPU/CPU 能力
- 實作自動選擇邏輯：NVIDIA GPU → PyTorch CUDA，AMD/Intel GPU → Vulkan，僅 CPU → OpenVINO INT8，低 RAM → sherpa-onnx
- 在 `airtype/utils/model_manager.py` 中實作 `ModelManager`，用於 HuggingFace 模型下載，包含進度回報、完整性檢查（SHA-256）、備用 URL 與磁碟空間驗證

## 功能

### 新增功能

- `hardware-detection`：GPU/CPU 能力偵測與自動推理路徑建議
- `model-download`：模型下載管理器，包含完整性驗證、進度回報與備用 URL

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/utils/hardware_detect.py`、`airtype/utils/model_manager.py`、`tests/test_hardware_detect.py`、`tests/test_model_manager.py`
- 無新增沉重依賴（GPU 偵測使用 subprocess，下載使用 urllib/httpx）
- 相依：06-asr-abstraction（模型登錄檔，用於得知哪些模型可用）
