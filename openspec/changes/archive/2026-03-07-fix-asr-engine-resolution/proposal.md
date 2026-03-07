## Why

專案中存在兩個同性質的「模型名稱 vs. 實際識別碼」不匹配問題，導致核心功能失效：

1. **ASR 引擎**：`load_default_engine()` 將設定檔中的模型名稱（`"qwen3-asr-0.6b"`）直接當作引擎 ID 查詢引擎註冊表，但註冊表中的 key 是引擎 ID（如 `"qwen3-vulkan"`、`"qwen3-openvino"`），導致 `KeyError` → `asr_engine=None` → `BatchRecognitionPipeline` 未建立 → 語音無法轉文字。設定中的 `voice.asr_inference_backend`（預設 `"auto"`）也從未被使用。

2. **LLM 潤飾**：`PolishEngine._get_local_engine()` 將 `llm.local_model`（值為模型 ID `"qwen2.5-1.5b-instruct-q4_k_m"`）直接當作檔案路徑傳給 `Llama(model_path=...)`，但實際 GGUF 檔案位於 `~/.airtype/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`。首次潤飾時 `PolishError` → 靜默回退至原始文字，潤飾功能永遠無法工作。

## What Changes

- 在 `ASREngineRegistry` 中新增**模型名稱 → 引擎 ID** 的解析邏輯
- `load_default_engine()` 結合 `asr_model`（模型名稱）與 `asr_inference_backend`（後端偏好）自動選擇已登錄的正確引擎
- 當 `backend="auto"` 時按優先順序嘗試已登錄的引擎（openvino → pytorch-cuda → vulkan）
- 若 `asr_model` 值恰好就是引擎 ID（向下相容），直接使用
- 在 `PolishEngine._get_local_engine()` 中新增**模型 ID → 檔案路徑**的解析邏輯，透過 `models/manifest.json` 查詢 filename，組合成 `~/.airtype/models/{filename}` 完整路徑

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `asr-abstraction`：`ASREngineRegistry.load_default_engine()` 新增模型名稱解析與後端自動選擇邏輯
- `llm-polish-engine`：`PolishEngine._get_local_engine()` 新增模型 ID → 檔案路徑解析邏輯

## Impact

- 受影響程式碼：`airtype/core/asr_engine.py`（`load_default_engine()` 方法）、`airtype/core/llm_polish.py`（`_get_local_engine()` 方法）
- 參考資料：`models/manifest.json`（模型 ID → filename 映射）
- 受影響設定：`~/.airtype/config.json` 中 `voice.asr_model`、`voice.asr_inference_backend`、`llm.local_model` 的語義得到正確實現
- 無 API 破壞性變更、無新增依賴
