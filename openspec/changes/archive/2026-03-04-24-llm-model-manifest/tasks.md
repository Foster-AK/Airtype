## 1. Manifest Schema 擴充

- [x] 1.1 更新 `models/manifest.json`，在所有現有 ASR 模型條目加入 `category`、`has_thinking_mode`、`thinking_disable_token` 欄位（LLM Model Manifest Schema Backward Compatibility；擴充 manifest schema 加入 category 與 thinking mode 欄位）— 驗證：每個 ASR 條目有 `category="asr"`, `has_thinking_mode=false`, `thinking_disable_token=null`
- [x] 1.2 在 `models/manifest.json` 新增三個 LLM GGUF 模型條目：qwen2.5-1.5b-instruct-q4_k_m、qwen2.5-3b-instruct-q4_k_m、qwen2.5-7b-instruct-q4_k_m（LLM GGUF Model Entries；LLM Model Category Field；Thinking Mode Declaration Fields；採用 Qwen2.5 Instruct 系列作為預設 LLM 模型）— 驗證：三個條目均有 `category="llm"`, `has_thinking_mode=false`, `thinking_disable_token=null`，URL 指向 HuggingFace bartowski 量化版

## 2. HardwareDetector 擴充

- [x] 2.1 [P] 在 `airtype/utils/hardware_detect.py` 的 `HardwareDetector` 新增 `recommend_llm()` 方法，實作五分支決策樹（LLM Inference Recommendation；以決策樹實作 recommend_llm() 方法）— 驗證：回傳 dataclass 含 `model`、`backend`、`warning` 欄位；CPU+RAM<8GB 時 `backend="disabled"`

## 3. ModelManager 分類查詢

- [x] 3.1 [P] 在 `airtype/utils/model_manager.py` 新增 `list_models_by_category(category)` 方法，從已載入的 manifest 篩選符合類別的條目（Category-Filtered Model Listing；ModelManager 分類查詢方法分離 ASR 與 LLM 模型）— 驗證：`list_models_by_category("asr")` 只回傳 ASR 條目；未知類別回傳空 list

## 4. Settings Voice 更新

- [x] 4.1 更新 `airtype/ui/settings_voice.py`，ASR 模型下拉選單改為呼叫 `list_models_by_category("asr")` 動態載入，並在硬體建議項目標示「（建議）」（Manifest-Driven ASR Model List；Voice Settings Page；使用者模型覆寫儲存於 config，預設值來自 recommend()）— 驗證：下拉選單條目數等於 manifest ASR 條目數；建議項目有「（建議）」標記
- [x] 4.2 更新 `airtype/ui/settings_voice.py`，使用者選擇後寫入 `config.asr.selected_model`；未下載的模型顯示下載指示符（Undownloaded Model Indicated）— 驗證：切換模型後 config 持久化；未下載模型顯示「↓」

## 5. 測試

- [x] 5.1 在 `tests/test_hardware_detect.py` 新增 `recommend_llm()` 的單元測試，涵蓋所有五個分支（NVIDIA 高 VRAM、NVIDIA 中 VRAM、AMD/Intel GPU、CPU+RAM≥8GB、CPU+RAM<8GB）— 驗證：`backend="disabled"` 分支有斷言；`warning="approaching_timeout_cpu"` 分支有斷言
- [x] 5.2 在 `tests/test_model_manager.py` 新增 `list_models_by_category()` 的單元測試（Category-Filtered Model Listing）— 驗證：分類過濾正確；未知類別回傳空 list
