## Why

Airtype 在 Windows 和 macOS 上啟動時都出現 `RecognitionPipeline 未建立（asr_engine=None）`，語音輸入功能完全無法使用。問題包含三個面向：

1. **macOS PyInstaller 打包遺漏**：ASR 引擎模組透過 `importlib.import_module()` 動態載入，PyInstaller 無法自動偵測，導致打包後的 `.app` 中完全不包含引擎模組。
2. **Windows 模型下載不完整**：模型目錄存在但缺少關鍵檔案（`encoder.onnx`、`embed_tokens.bin`），現有程式碼只檢查目錄是否存在，不驗證內容完整性。
3. **診斷資訊不足**：引擎載入失敗用 `logger.debug` 記錄（INFO 級別看不到），且 `load_default_engine` 靜默失敗後外層誤判為成功。

## What Changes

- **PyInstaller spec**：在 `hiddenimports` 加入所有動態載入的 ASR 引擎模組與共用模組
- **啟動日誌**：將引擎模組載入失敗的日誌從 `debug` 提升至 `warning`
- **成功判斷**：以 `active_engine is not None` 判斷引擎是否真正載入，取代依賴 try/except 的隱含邏輯
- **模型完整性驗證**：新增 `ModelManager.validate_model_files()` 方法，支援 `"A OR B"` 語法的必要檔案清單
- **引擎必要檔案宣告**：在 `QwenOnnxEngine` 新增 `REQUIRED_FILES` 類別屬性
- **啟動預檢**：在 `load_default_engine` 前驗證模型檔案完整性
- **警告對話框**：區分「模型未下載」vs「模型不完整」，顯示具體缺少的檔案

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `packaging`：`hiddenimports` 新增動態載入的 ASR 引擎模組
- `main-wiring`：啟動流程新增模型完整性預檢、修正引擎載入成功判斷、提升日誌級別
- `model-download`：新增 `validate_model_files()` 模型檔案完整性驗證方法

## Impact

- 受影響程式碼：
  - `airtype.spec`（PyInstaller 打包設定）
  - `airtype/__main__.py`（啟動流程 4 處修改）
  - `airtype/utils/model_manager.py`（新增驗證方法）
  - `airtype/core/asr_qwen_onnx.py`（新增 `REQUIRED_FILES` 屬性）
- 無 API 變更、無設定格式變更
- 依賴：無其他 change 依賴
