## 1. Silero VAD 整合

- [x] 1.1 將 `onnxruntime` 加入 `pyproject.toml` 依賴
- [x] 1.2 建立 `airtype/core/vad.py`，透過 ONNX Runtime 整合 Silero VAD v5：載入模型、對 512 樣本幀執行推理、回傳語音機率 — 驗證：語音機率偵測需求
- [x] 1.3 依設計將 `silero_vad_v5.onnx` 模型檔案內建於 `models/vad/` — 驗證：內建模型檔案

## 2. VAD 狀態機

- [x] 2.1 實作搭配事件 callback 的四狀態機：IDLE → SPEECH → SILENCE_COUNTING → SPEECH_ENDED，轉換依規格 — 驗證：VAD 狀態機需求
- [x] 2.2 實作可設定參數：從設定讀取語音門檻值與靜默逾時 — 驗證：可設定參數需求
- [x] 2.3 透過 callback 註冊（`on_state_change`）實作狀態轉換事件 — 驗證：狀態轉換事件需求

## 3. 整合

- [x] 3.1 將 VadEngine 連接至 AudioCaptureService queue 以消費音訊幀

## 4. 測試

- [x] 4.1 撰寫 VAD 狀態機轉換的單元測試（全部 4 個狀態、所有轉換）
- [x] 4.2 撰寫可設定靜默逾時行為的單元測試
- [x] 4.3 撰寫整合測試：輸入已知語音/靜默音訊 → 驗證狀態轉換
