## 為什麼

選用性的 LLM 後處理可透過修正標點符號、同音字與文法來提升 ASR 輸出品質。支援本機（llama.cpp）與 API（OpenAI 相容）兩種後端，並提供比對原始文字與潤飾後文字的預覽 UI。

參考：PRD §5.4（LLM 潤飾設定）、§6.4（LLM 潤飾引擎）。

相依性：13-core-controller、16-settings-panel、24-llm-model-manifest（manifest schema 擴充、`recommend_llm()` 方法）。

## 變更內容

- 透過 llama-cpp-python（GGUF 模型）實作本機 LLM 引擎
- 實作 API 整合（Anthropic、OpenAI、Ollama、自訂端點）
- 實作 3 種潤飾模式：輕度（僅標點）、中度（+流暢度）、完整（+文法）
- 實作潤飾預覽比對 UI
- 在設定面板新增 LLM 設定頁面
- **（新增）** 讀取 manifest 的 `has_thinking_mode` / `thinking_disable_token`，推理前套用 thinking 抑制 token
- **（新增）** `SettingsLlmPage` 呼叫 `HardwareDetector.recommend_llm()`，顯示 CPU-only 逾時警示

## 功能

### 新增功能

- `llm-polish-engine`：具可設定模式的本機與 API LLM 文字潤飾
- `llm-api-integration`：用於雲端 LLM 潤飾的 OpenAI 相容 API 整合
- `llm-thinking-mode`：本機推理前讀取 manifest thinking mode 欄位並套用抑制 token
- `llm-hardware-warning`：設定頁面顯示硬體推薦警示（CPU-only 逾時風險）

### 修改功能

- `llm-polish-engine`：擴充 `LocalLLMEngine` 讀取 manifest `has_thinking_mode` / `thinking_disable_token`

## 影響

- 新增檔案：`airtype/core/llm_polish.py`、`airtype/ui/settings_llm.py`、`tests/test_llm_polish.py`
- 新增選用相依套件：`llama-cpp-python`、`httpx`（用於 API 呼叫）
- 相依於：13-core-controller、16-settings-panel、24-llm-model-manifest
