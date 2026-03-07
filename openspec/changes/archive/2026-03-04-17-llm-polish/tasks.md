## 1. 本機 LLM 引擎

- [x] 1.1 建立 `airtype/core/llm_polish.py` 實作本機 LLM 潤飾，採用 llama-cpp-python 進行本機 LLM 推理（GGUF 模型、4096 context、3 秒逾時）— 驗證：Local LLM Polishing、Local LLM Inference via llama-cpp-python、以 llama-cpp-python 進行本機 LLM 推理
- [x] 1.2 實作以提示詞模板變體實現的潤飾模式：輕度、中度、完整，支援自訂提示詞覆寫 — 驗證：Polishing Modes Implemented via Prompt Template Variants、以提示詞模板變體實作潤飾模式

## 2. API 整合

- [x] 2.1 實作透過 httpx 呼叫 OpenAI 相容 API：支援 Anthropic、OpenAI、Ollama、自訂端點 — 驗證：OpenAI-Compatible API Integration、OpenAI-Compatible API Calls via httpx、透過 httpx 呼叫 OpenAI 相容 API 需求
- [x] 2.2 實作 API 錯誤處理，失敗時回退至原始文字

## 3. UI

- [x] 3.1 實作潤飾預覽 UI：原始文字與潤飾後文字並排顯示並供選擇 — 驗證：Polish Preview UI 需求
- [x] 3.2 建立 `airtype/ui/settings_llm.py` 實作 LLM 設定頁面（模型選擇、API 設定、模式選擇）

## 4. 相依套件

- [x] 4.1 將 `llama-cpp-python` 與 `httpx` 加入 `pyproject.toml` 選用相依套件

## 5. 測試

- [x] 5.1 撰寫潤飾引擎單元測試（模擬 llama.cpp、測試 3 種模式、測試逾時）
- [x] 5.2 撰寫 API 整合單元測試（模擬 httpx、測試錯誤回退）

## 6. Thinking Mode 抑制（來自 24-llm-model-manifest）

- [x] 6.1 在 `airtype/core/llm_polish.py` 的 `LocalLLMEngine` 新增 manifest 讀取邏輯：根據 `config.llm.local_model` 查找 `models/manifest.json` 對應條目，取得 `has_thinking_mode` 與 `thinking_disable_token` — 驗證：Thinking Mode Token Suppression 需求、Manifest Entry Not Found 場景
- [x] 6.2 在 `LocalLLMEngine.polish()` 中，若 `has_thinking_mode=True` 且 `thinking_disable_token` 非空，則在 prompt 前綴插入該 token — 驗證：Model With Thinking Mode and Disable Token 場景、Model Without Thinking Mode 場景

## 7. 硬體警示 UI（來自 24-llm-model-manifest）

- [x] 7.1 在 `airtype/ui/settings_llm.py` 的 `SettingsLlmPage.__init__()` 呼叫 `HardwareDetector.recommend_llm()`，若 `warning="approaching_timeout_cpu"` 則顯示黃色警示標籤 — 驗證：Hardware Recommendation Warning in LLM Settings UI 需求、Showing CPU Timeout Warning 場景、HardwareDetector Unavailable 場景

## 8. 新增測試（Thinking Mode + 硬體警示）

- [x] 8.1 在 `tests/test_llm_polish.py` 新增 thinking mode 單元測試：mock manifest 回傳 `has_thinking_mode=True`，驗證 `thinking_disable_token` 被正確前綴至 prompt；mock `has_thinking_mode=False`，驗證 prompt 不變 — 驗證：Thinking Mode Token Suppression 需求
- [x] 8.2 在 `tests/test_llm_polish.py` 新增 manifest entry 不存在測試：驗證無 manifest 條目時 `LocalLLMEngine` 正常運作不拋出例外 — 驗證：Manifest Entry Not Found 場景

## 9. Qwen2.5 引擎精化（根據模型大小自動降級潤飾模式 + Pre/Post Clean + Few-shot + Sampling）

- [x] [P] 9.1 在 `airtype/core/llm_polish.py` 的 `LocalLLMEngine.__init__()` 加入 `model_size_b: float` 參數，實作 `_resolve_mode()` 方法依閾值（FULL≥3B、MEDIUM≥1.5B、LIGHT≥0B）自動降級（根據模型大小自動降級潤飾模式），`PolishResult` 回傳實際使用的模式 — 驗證：Model Size Auto-Downgrade 需求、Auto-downgrade FULL to MEDIUM 場景、Auto-downgrade to LIGHT 場景
- [x] [P] 9.2 在 `LocalLLMEngine` 加入 `_pre_clean()` 與 `_post_clean()` 靜態方法（ASR 輸出前處理（pre_clean）與 LLM 輸出後處理（post_clean））：pre_clean 以 regex 壓縮連續語氣詞、重複贅詞，移除多餘空白；post_clean 移除廢話前綴（好的、以下是等）、markdown 包裹、首尾引號 — 驗證：ASR Output Pre-cleaning、LLM Output Post-cleaning 需求、Pre-clean repeated fillers 場景、Post-clean preamble prefix 場景
- [x] [P] 9.3 將三種模式的 `_SYSTEM_PROMPTS` 更新為含 few-shot 範例的精簡版本（提示詞採 few-shot 範例設計）：LIGHT/MEDIUM/FULL 各一組繁體中文 input→output 示範，末尾加「直接輸出結果，不要加任何說明。」；改用 `Qwen2.5 直接呼叫 create_chat_completion（無需手動組裝 ChatML）`；n_ctx 從 2048 上調至 4096，max_tokens 改為 `max(input_len × 3, 256)`；`llm.custom_prompt` 自訂覆寫優先級不變（設定後取代內建 prompt，適用全部模式） — 驗證：Few-shot Prompt Templates 需求、Custom prompt 場景、Local LLM Inference via llama-cpp-python 需求
- [x] [P] 9.4 將 `create_chat_completion()` 的採樣參數（Sampling Parameters）統一設定為 `temperature=0.1, top_p=0.8, top_k=20, min_p=0.0, repeat_penalty=1.1`；`stop=["<|im_end|>"]` — 驗證：Sampling Parameters Configuration 需求、Deterministic output 場景
- [x] 9.5 在 `tests/test_llm_polish.py` 新增 Qwen2.5 精化單元測試：測試 `_resolve_mode()` 三種降級情境（0.5B/1.5B/3B 各請求 FULL）、測試 `_pre_clean()` 壓縮語氣詞及贅詞、測試 `_post_clean()` 移除常見廢話前綴及引號包裹、測試 `custom_prompt` 設定後確實取代內建 prompt — 驗證：Model Size Auto-Downgrade、ASR Output Pre-cleaning、LLM Output Post-cleaning、Custom prompt 場景
