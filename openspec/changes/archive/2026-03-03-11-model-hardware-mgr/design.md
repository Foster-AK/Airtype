## 背景

首次使用者體驗取決於自動硬體偵測與無縫模型下載。PRD §10.4 定義了偵測 → 建議 → 下載的流程。

相依性：06-asr-abstraction。

## 目標 / 非目標

**目標：**

- 偵測 GPU 廠商/VRAM、CPU 類型、可用 RAM
- 自動建議最佳推理路徑與模型
- 從 HuggingFace 下載模型，包含進度、完整性檢查、備用 URL
- 下載前檢查磁碟空間

**非目標：**

- 不進行模型訓練或微調
- 不進行模型轉換（使用者下載已轉換的模型）

## 決策

### 透過 subprocess 呼叫進行 GPU 偵測

Windows：`nvidia-smi` 偵測 NVIDIA，WMI 查詢偵測 AMD/Intel。macOS：`system_profiler`。Linux：`lspci` + `nvidia-smi`。解析輸出取得 GPU 型號與 VRAM。

**為何使用 subprocess 而非 GPU 函式庫**：避免沉重依賴（pycuda、vulkan 繫結）。subprocess 足以進行偵測。

### 以決策樹實作建議邏輯

遵循 PRD §10.4 決策樹：NVIDIA GPU（VRAM≥4GB）→ PyTorch CUDA 1.7B；NVIDIA（VRAM≥2GB）→ PyTorch CUDA 0.6B；AMD/Intel GPU → Vulkan 0.6B；CPU（RAM≥6GB）→ OpenVINO INT8 0.6B；CPU（RAM<6GB）→ sherpa-onnx SenseVoice。

### 透過 huggingface-hub 或 httpx 從 HuggingFace 下載

若可用則使用 `huggingface_hub.hf_hub_download`，否則以 httpx 直接 HTTPS。支援中斷下載後續傳。下載完成後以 SHA-256 驗證完整性。

### 模型 manifest JSON

`models/manifest.json` 描述可用模型及其 ID、大小、URL 與校驗碼。模型管理器讀取此檔案以得知可用項目。

## 風險 / 取捨

- [風險] GPU 偵測在非常見硬體上可能失敗 → 緩解措施：退回至 CPU 建議；使用者可在設定中覆寫
- [風險] HuggingFace 下載在某些地區可能緩慢或被封鎖 → 緩解措施：依 PRD §6.3.7 提供備用 URL
- [取捨] huggingface_hub 新增依賴 → 可選；退回至直接 HTTP 下載
