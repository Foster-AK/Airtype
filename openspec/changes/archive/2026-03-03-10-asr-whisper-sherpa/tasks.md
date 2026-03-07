## 1. Breeze-ASR-25 引擎

- [x] 1.1 建立 `airtype/core/asr_breeze.py`，實作 `BreezeAsrEngine`，優先使用 faster-whisper 而非 HuggingFace pipeline 進行批次辨識 — 驗證：Breeze-ASR-25 批次辨識需求
- [x] 1.2 實作 Breeze 中英混合語句的語碼轉換支援 — 驗證：Breeze 語碼轉換支援需求
- [x] 1.3 實作 Breeze 引擎註冊為 "breeze-asr-25" — 驗證：Breeze 引擎註冊需求

## 2. sherpa-onnx 引擎

- [x] 2.1 建立 `airtype/core/asr_sherpa.py`，實作 `SherpaOnnxEngine`，使用 sherpa-onnx Python 繫結搭配 SenseVoice 與 Paraformer 的 OfflineRecognizer — 驗證：sherpa-onnx 離線辨識需求
- [x] 2.2 透過 OnlineRecognizer 實作 sherpa-onnx 串流辨識 — 驗證：sherpa-onnx 串流辨識需求
- [x] 2.3 透過 hotwords_file 參數實作 sherpa-onnx 熱詞 — 驗證：sherpa-onnx 熱詞需求
- [x] 2.4 實作 sherpa-onnx 引擎註冊為 "sherpa-sensevoice" 與 "sherpa-paraformer" — 驗證：sherpa-onnx 引擎註冊需求

## 3. 依賴

- [x] 3.1 將 `faster-whisper`、`transformers`、`sherpa-onnx` 作為可選依賴加入 `pyproject.toml`

## 4. 測試

- [x] 4.1 撰寫使用 mock faster-whisper 的 BreezeAsrEngine 單元測試
- [x] 4.2 撰寫使用 mock sherpa-onnx 的 SherpaOnnxEngine 單元測試
- [x] 4.3 撰寫整合測試（模型未下載時跳過）
