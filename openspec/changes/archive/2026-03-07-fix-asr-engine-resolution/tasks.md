## 1. ASR 模型名稱到引擎 ID 映射表

- [x] [P] 1.1 在 `airtype/core/asr_engine.py` 模組層級新增 `_MODEL_ENGINE_MAP` 字典，定義模型名稱到引擎 ID 候選清單的映射（對應 design「ASR 模型名稱到引擎 ID 映射表」決策）。驗證：字典包含 `qwen3-asr-0.6b`、`breeze-asr-25`、`sherpa-sensevoice`、`sherpa-paraformer` 四組映射。

## 2. ASR load_default_engine 解析策略

- [x] 2.1 修改 `ASREngineRegistry.load_default_engine()` 方法，實作三階段解析邏輯：(1) 直接匹配引擎 ID、(2) 映射解析 + auto 遍歷、(3) 特定 backend 子字串匹配（對應 design「load_default_engine 解析策略」與「後端關鍵字匹配規則」決策）。滿足 spec「Load Default Engine from Configuration」需求。驗證：方法讀取 `config.voice.asr_model` 與 `config.voice.asr_inference_backend` 並正確解析。

## 3. LLM 模型 ID 到檔案路徑解析

- [x] [P] 3.1 修改 `PolishEngine._get_local_engine()`，新增模型 ID → 檔案路徑解析邏輯（對應 design「LLM 模型 ID 到檔案路徑解析」決策）。滿足 spec「Local LLM Inference via llama-cpp-python」需求。流程：(1) 若 `local_model` 已是有效檔案路徑則直接使用、(2) 查詢 `models/manifest.json` 取得 filename、(3) 組合 `~/.airtype/models/{filename}`、(4) 找不到則拋出 `PolishError`。驗證：`llm.local_model="qwen2.5-1.5b-instruct-q4_k_m"` 能解析為 `~/.airtype/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`。

## 4. ASR 測試

- [x] [P] 4.1 新增單元測試：模型名稱 + auto backend 解析至已登錄引擎（對應 spec scenario「Model Name Resolves to Registered Engine via Auto Backend」）。驗證：`asr_model="qwen3-asr-0.6b"` + `backend="auto"` 且僅 `qwen3-vulkan` 已登錄時，正確載入 `qwen3-vulkan`。
- [x] [P] 4.2 新增單元測試：模型名稱 + 特定 backend 解析（對應 spec scenario「Model Name Resolves via Specific Backend」）。驗證：`asr_model="qwen3-asr-0.6b"` + `backend="openvino"` 且 `qwen3-openvino` 已登錄時，正確載入。
- [x] [P] 4.3 新增單元測試：直接引擎 ID 向下相容（對應 spec scenario「Direct Engine ID Still Works」）。驗證：`asr_model="qwen3-vulkan"` 直接載入。
- [x] [P] 4.4 新增單元測試：模型名稱但無已登錄後端、未知模型名稱（對應 spec scenario「Model Name With No Registered Backend」與「Configuration Specifies an Unknown Model」）。驗證：兩種情況均記錄 WARNING 且 `active_engine` 為 None。

## 5. LLM 測試

- [x] [P] 5.1 新增單元測試：模型 ID 透過 manifest 解析為檔案路徑（對應 spec scenario「Loading a local model by model ID」）。驗證：`local_model="qwen2.5-1.5b-instruct-q4_k_m"` 解析為正確的 GGUF 路徑。
- [x] [P] 5.2 新增單元測試：直接檔案路徑向下相容（對應 spec scenario「Loading a local model by direct file path」）。驗證：`local_model="/path/to/model.gguf"` 直接使用。
- [x] [P] 5.3 新增單元測試：manifest 中找不到模型 ID（對應 spec scenario「Model ID not found in manifest」）。驗證：拋出 `PolishError` 附帶清楚訊息。

## 6. 端對端驗證

- [x] 6.1 啟動 `python -m airtype`，確認日誌顯示「預設 ASR 引擎已載入」與「BatchRecognitionPipeline 已建立」，按 Ctrl+Shift+Space 語音輸入後文字成功注入。確認 LLM 潤飾日誌顯示「本機 LLM 模型已載入」且潤飾功能正常運作。
