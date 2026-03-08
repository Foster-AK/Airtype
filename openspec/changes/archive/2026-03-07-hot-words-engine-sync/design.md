## Context

fix-hot-words 已修復啟動時熱詞注入和 sherpa-onnx hotwords_file 傳遞。但驗證發現兩個遺留問題：
1. `ASREngineRegistry.set_active_engine()` 切換引擎後不會觸發 `sync_hot_words()`。
2. Qwen3-ASR 等不支援熱詞的引擎在 UI 無任何提示，用戶可能花時間設定熱詞卻不知道無效。

目前涉及的程式碼路徑：
- `airtype/core/asr_engine.py:259-298`：`set_active_engine()` 完成切換但無 callback 機制
- `airtype/core/asr_engine.py:167`：Protocol 的 `set_hot_words()` 定義，無 `supports_hot_words` 屬性
- `airtype/ui/settings_dictionary.py`：辭典設定頁面，無引擎能力判斷邏輯

## Goals / Non-Goals

**Goals:**

- 引擎切換後自動重新注入熱詞
- 各引擎能回報是否支援熱詞
- 辭典 UI 在不支援熱詞的引擎下顯示警告提示

**Non-Goals:**

- 不為 Qwen3-ASR 實作原生熱詞支援
- 不改變辭典引擎的資料模型
- 不禁用熱詞編輯（即使引擎不支援也允許設定，以便切換引擎後生效）

## Decisions

### ASREngineRegistry 引擎切換 callback

在 `ASREngineRegistry` 新增 `on_engine_changed` callback 屬性（`Optional[Callable[[str], None]]`），在 `set_active_engine()` 完成切換後呼叫。`__main__.py` 在初始化時設定此 callback 為 `_sync_hot_words_callback`。

**替代方案**：在 `set_active_engine()` 內部直接呼叫 `sync_hot_words()`。不採用是因為 Registry 不應持有 DictionaryEngine 引用，職責分離更佳。

### supports_hot_words 屬性

在 ASREngine Protocol 新增 `supports_hot_words: bool` 屬性（只讀 property）。
- sherpa-onnx：回報 `True`
- Qwen3-ASR（OpenVINO / PyTorch / Vulkan）、Breeze-ASR：回報 `False`

**替代方案**：使用 `engine_capabilities()` 回傳能力字典。不採用是因為目前只需判斷熱詞支援，單一布林值更簡潔。

### 辭典 UI 警告標籤

在 `SettingsDictionaryPage` 的熱詞區塊（`_hw_group`）頂部加入 `QLabel` 警告標籤，文字為「目前引擎不支援熱詞偏置，建議使用替換規則達成相同效果」。透過 `_on_hot_words_changed` 同一個 callback 傳入引擎狀態，或新增 `asr_engine` 參數讓 UI 直接查詢 `supports_hot_words`。

選擇方案：SettingsDictionaryPage 接受 `asr_registry` 參數（Optional），在顯示時查詢 `active_engine.supports_hot_words`。引擎切換後由 callback 觸發 UI 更新。

## Risks / Trade-offs

- **[風險] Property 新增可能破壞現有 mock 測試** → 為現有 mock 加上 `supports_hot_words = True` 預設值。
- **[取捨] 不禁用熱詞 UI**：引擎不支援時仍允許編輯（因為用戶可能稍後切換引擎），只顯示提示。
