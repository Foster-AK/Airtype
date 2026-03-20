## 1. PyInstaller Hidden Imports 策略

- [x] [P] 1.1 在 `airtype.spec` 的 `hiddenimports` 加入所有動態載入的 ASR 引擎模組（`airtype.core.asr_qwen_onnx`、`airtype.core.asr_qwen_pytorch`、`airtype.core.asr_qwen_vulkan`、`airtype.core.asr_qwen_mlx`、`airtype.core.asr_sherpa`、`airtype.core.asr_breeze`）與共用模組（`airtype.core.asr_engine`、`airtype.core.asr_utils`、`airtype.core.processor_numpy`），滿足 Single Executable via PyInstaller 中 Dynamically Loaded ASR Engine Modules Included 的場景

## 2. ASR Engine Required Files Declaration

- [x] [P] 2.1 在 `airtype/core/asr_qwen_onnx.py` 的 `QwenOnnxEngine` 類別新增 `REQUIRED_FILES` 類別屬性，包含 `encoder.onnx OR encoder.int8.onnx`、`decoder_init.onnx OR decoder_init.int8.onnx`、`decoder_step.onnx OR decoder_step.int8.onnx`、`embed_tokens.bin`、`config.json`，滿足 ASR Engine Required Files Declaration 的需求

## 3. 模型完整性驗證架構（Model File Integrity Validation）

- [x] 3.1 在 `airtype/utils/model_manager.py` 新增 `validate_model_files(model_id, required_files)` 方法，回傳 `(is_valid, missing_files, tmp_files)` 三元組，支援 `"A OR B"` 語法與 `.tmp` 檔偵測，滿足 Model File Integrity Validation 的所有場景
- [x] 3.2 為 `validate_model_files()` 撰寫單元測試，涵蓋：全部檔案存在、缺少必要檔案、OR 語法滿足/不滿足、`.tmp` 檔偵測、`required_files=None` 等場景

## 4. Application Entry Point Component Wiring 修正

- [x] 4.1 日誌級別提升：在 `airtype/__main__.py` 將引擎模組載入失敗的日誌從 `logger.debug` 提升至 `logger.warning`（第 191 行），滿足 Engine Registration Failure Logged at Warning Level 場景
- [x] 4.2 引擎載入成功判斷修正：修改 `airtype/__main__.py` 的 Application Entry Point Component Wiring 邏輯，移除 try 區塊內的 `logger.info`，改為在取得 `asr_engine` 後以 `active_engine is not None` 判斷並分別記錄 INFO/WARNING，滿足 ASR Engine Load Success/Failure Accurately Reported 場景
- [x] 4.3 在 `airtype/__main__.py` 的 `load_default_engine` 前插入模型完整性預檢邏輯，使用 `ModelManager.validate_model_files()` 驗證配置的模型，將結果存入 `model_integrity_msg`，滿足 Model Integrity Pre-check Detects Incomplete Download 場景
- [x] 4.4 修改 `airtype/__main__.py` 的 ASR 缺失警告對話框（第 342-353 行），依據 `model_integrity_msg` 區分「模型未下載」與「模型不完整」兩種訊息，滿足 Graceful Degradation on Component Failure 中 ASR Warning Dialog Shows Incomplete Model Details 與 ASR Warning Dialog Shows No Model Downloaded 場景

## 5. 驗證

- [x] 5.1 在 Windows 上啟動 Airtype（模型完整），確認 ASR 引擎成功載入且無多餘警告
- [x] 5.2 在 Windows 上模擬模型不完整（移除 encoder.onnx），確認警告對話框顯示缺少的具體檔案
