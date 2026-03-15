## 1. 依賴與專案設定

- [x] [P] 1.1 在 `pyproject.toml` 新增 `mlx` optional dependency group（`mlx>=0.18.0`, `mlx-qwen3-asr>=0.1.0`），僅 macOS 條件安裝策略
  - 測試：`pip install -e ".[mlx]"` 在 macOS 上成功安裝
- [x] [P] 1.2 在 `models/manifest.json` 新增 MLX 模型條目（`qwen3-asr-0.6b-mlx`），配置模型格式與下載機制（HuggingFace safetensors），包含 model_id、HuggingFace repo、inference_engine 欄位
  - 測試：manifest JSON 解析無誤，條目包含所有必要欄位

## 2. MLX 引擎核心實作

- [x] 2.1 建立 `airtype/core/asr_qwen_mlx.py`，實作 `MLXQwen3ASREngine` 類別，遵循 `ASREngine` Protocol — 包含 MLX Model Loading（`load_model` 接受 HuggingFace ID 或本地路徑，使用 MLX Session API 封裝策略）
  - 測試：在 macOS Apple Silicon 上 `load_model("Qwen/Qwen3-ASR-0.6B", {})` 成功載入模型
- [x] 2.2 實作 Batch Speech Recognition（`recognize()` 方法），接受 16kHz mono PCM float32 `np.ndarray`，透過 `Session.transcribe()` 進行推理，使用 MLX 內建音訊前處理路徑，回傳 `ASRResult`
  - 測試：傳入 5 秒中文音訊，回傳含文字、語言代碼、信心分數的 `ASRResult`
- [x] 2.3 實作 Context Text Biasing（`set_context()` 方法），將 context text 傳遞至 `Session.transcribe()` 的 `context` 參數
  - 測試：設定 context text 後呼叫 `recognize()`，確認 context 被傳入 transcribe 呼叫
- [x] 2.4 實作 Lazy Model Loading（`prepare()` + `_ensure_loaded()` 延遲載入模式）
  - 測試：`prepare()` 後不載入模型；首次 `recognize()` 觸發載入；後續呼叫不重複載入
- [x] 2.5 實作 Model Unloading（`unload()` 方法），釋放 Session 與模型引用
  - 測試：`unload()` 後記憶體引用為 None；再次 `recognize()` 可觸發重新載入
- [x] 2.6 實作 Hot Words Property（`supports_hot_words` 回傳 `False`）與 Supported Languages（`get_supported_languages()` 回傳 `["zh-TW", "zh-CN", "en", "ja", "ko"]`）
  - 測試：屬性回傳值正確
- [x] 2.7 實作 Engine Registration（`register()` 函式），配置引擎 ID 與登錄位置（engine ID `qwen3-mlx`），嘗試 `import mlx`，成功則登錄至 registry
  - 測試：有 mlx 時回傳 `True` 且 registry 含 `qwen3-mlx`；無 mlx 時回傳 `False`

## 3. 整合與接線

- [x] [P] 3.1 更新 `airtype/__main__.py` 的 `_ENGINE_MODULE_MAP`，新增 `"airtype.core.asr_qwen_mlx"` 模組路徑，實作 Application Entry Point Component Wiring 的 MLX 部分
  - 測試：macOS 上 `asr_qwen_mlx` 模組被嘗試匯入；Windows/Linux 上靜默跳過
- [x] [P] 3.2 更新 `airtype/core/asr_engine.py` 的 `_MODEL_ENGINE_MAP`，在 `qwen3-asr-0.6b` 候選清單加入 `qwen3-mlx`，實作 Load Default Engine from Configuration 的 MLX 解析
  - 測試：`asr_inference_backend="mlx"` 時解析到 `qwen3-mlx`；`auto` 模式下若僅 `qwen3-mlx` 可用則選中

## 4. 硬體偵測擴充

- [x] 4.1 在 `airtype/utils/hardware.py` 新增 Apple Silicon 硬體偵測（Apple Silicon Detection，`is_apple_silicon` 欄位），檢查 `sys.platform == "darwin"` 且 `platform.machine() == "arm64"`
  - 測試：macOS ARM64 回傳 `True`；Windows x86_64 回傳 `False`
- [x] 4.2 更新 Inference Path Recommendation 決策樹，新增 Apple Silicon 分支：Apple Silicon → engine=`qwen3-mlx`, model=`qwen3-asr-0.6b`（優先於 CPU fallback）
  - 測試：Apple Silicon 環境推薦 `qwen3-mlx`

## 5. 測試

- [x] [P] 5.1 建立 `tests/test_asr_qwen_mlx.py`，覆蓋所有 spec 情境：MLX Model Loading、Batch Speech Recognition、Context Text Biasing、Lazy Model Loading、Model Unloading、Hot Words Property、Supported Languages、Engine Registration（使用 mock 避免實際 MLX 依賴）
  - 測試：`pytest tests/test_asr_qwen_mlx.py` 全部通過
- [x] [P] 5.2 更新 `tests/test_asr_engine.py`，新增 `qwen3-mlx` 在 `_MODEL_ENGINE_MAP` 中的解析測試
  - 測試：新增測試案例通過
- [x] [P] 5.3 更新 `tests/test_hardware.py`（或新增），測試 Apple Silicon Detection 與更新後的推薦決策樹
  - 測試：模擬 macOS ARM64 環境的推薦結果正確
