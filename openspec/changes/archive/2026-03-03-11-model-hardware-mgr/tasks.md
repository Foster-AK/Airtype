## 1. 硬體偵測

- [x] 1.1 建立 `airtype/utils/hardware_detect.py`，透過 subprocess 呼叫進行 GPU 偵測（nvidia-smi、WMI、system_profiler、lspci）— 驗證：GPU 偵測需求
- [x] 1.2 實作系統能力評估：CPU 類型、總 RAM、可用磁碟 — 驗證：系統能力評估需求
- [x] 1.3 依 PRD §10.4 以決策樹實作推理路徑建議邏輯 — 驗證：推理路徑建議需求

## 2. 模型下載管理器

- [x] 2.1 建立 `airtype/utils/model_manager.py`，透過 huggingface-hub 或 httpx 實作帶進度回報的模型下載 — 驗證：帶進度的模型下載需求
- [x] 2.2 實作下載完整性驗證（下載後 SHA-256）— 驗證：下載完整性驗證需求
- [x] 2.3 實作備用下載 URL：失敗時自動重試下一個 URL — 驗證：備用下載 URL 需求
- [x] 2.4 實作下載前磁碟空間驗證 — 驗證：磁碟空間驗證需求
- [x] 2.5 建立模型 manifest JSON 檔案 `models/manifest.json`，包含可用模型 — 驗證：模型 manifest 需求

## 3. 測試

- [x] 3.1 撰寫硬體偵測的單元測試（mock subprocess 輸出，涵蓋 NVIDIA、AMD、僅 CPU）
- [x] 3.2 撰寫建議邏輯的單元測試（決策樹所有分支）
- [x] 3.3 撰寫模型管理器的單元測試（mock 下載、校驗碼驗證、磁碟空間檢查）
