## 1. 引擎實作

- [x] 1.1 將 `openvino` 加入 `pyproject.toml` 可選依賴
- [x] 1.2 建立 `airtype/core/asr_qwen_openvino.py`，使用 openvino.Core 的 OpenVINO IR 模型載入實作 `QwenOpenVinoEngine`，用於 INT8 量化模型 — 驗證：OpenVINO INT8 模型載入需求
- [x] 1.3 實作批次語音辨識：接受來自 numpy-preprocessor 的 Mel 特徵、執行推理、將 token ID 解碼為文字 — 驗證：批次語音辨識需求
- [x] 1.4 實作透過提示 token 注入的上下文偏移：建構包含前置熱詞與上下文文字的 BPE 提示 — 驗證：透過提示注入實現上下文偏移需求
- [x] 1.5 實作延遲載入模型：在首次 `recognize()` 呼叫時載入模型，此後重用 — 驗證：延遲載入模型需求

## 2. 註冊

- [x] 2.1 實作引擎註冊：openvino 套件可用時自動註冊為 "qwen3-openvino" — 驗證：引擎註冊需求

## 3. 測試

- [x] 3.1 撰寫使用 mock OpenVINO 模型的單元測試（測試載入、推理流程、延遲載入）
- [x] 3.2 撰寫整合測試：載入真實 INT8 模型 → 辨識測試音訊 → 驗證文字輸出（模型不可用時跳過）
