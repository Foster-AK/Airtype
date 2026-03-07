## Why

Change 11 的 `ModelManager` 只涵蓋 ASR 模型下載，而 Change 17（LLM 潤飾）委派模型下載至 Change 11，形成規格缺口。需補充 LLM GGUF 模型的清單條目、manifest schema 擴充，以及硬體推薦決策樹。

參考：PRD §6.4（LLM 潤飾引擎）、§10.4（硬體自動偵測）。

相依性：11-model-hardware-mgr、17-llm-polish。

## What Changes

- 擴充 `models/manifest.json` schema，加入 `category`、`has_thinking_mode`、`thinking_disable_token` 欄位
- 新增 Qwen2.5 系列 GGUF 模型條目（1.5B / 3B / 7B，Q4_K_M 量化）至 manifest
- 擴充 `airtype/utils/hardware_detect.py` 的 `HardwareDetector`，加入 `recommend_llm()` 方法與 LLM 推薦決策樹
- 低階 CPU（RAM < 8GB）建議停用本地 LLM 潤飾（`backend="disabled"`）
- 在 `airtype/utils/model_manager.py` 新增 `list_models_by_category()` 方法，明確分離 ASR 與 LLM 模型查詢路徑
- 設定 Voice 頁面的 ASR 模型下拉選單改為從 manifest 動態載入（category="asr"），並標示硬體建議項目；LLM 設定頁面同理（屬 Change 17）

## Capabilities

### New Capabilities

- `llm-model-manifest`：LLM GGUF 模型清單條目與 manifest schema 擴充，支援 thinking mode 宣告

### Modified Capabilities

- `hardware-detection`：擴充 `HardwareDetector`，加入 `recommend_llm()` 方法（LLM 推薦決策樹）
- `model-download`：`ModelManager` 新增 `list_models_by_category()` 方法，支援 ASR/LLM 分類查詢
- `settings-voice`：ASR 模型下拉選單改為從 manifest 動態載入，顯示硬體建議標記

## Impact

- 修改檔案：`models/manifest.json`、`airtype/utils/hardware_detect.py`、`airtype/utils/model_manager.py`、`airtype/ui/settings_voice.py`
- 新增測試：`tests/test_hardware_detect.py`（新增 LLM 推薦測試案例）、`tests/test_model_manager.py`（新增分類查詢測試）
- 相依：11-model-hardware-mgr（`ModelManager` 下載機制複用）
- 相依：17-llm-polish（讀取 manifest 的 `has_thinking_mode` 與 `thinking_disable_token`）
