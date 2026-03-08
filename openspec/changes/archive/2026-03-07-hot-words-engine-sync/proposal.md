## Why

fix-hot-words change 修復了熱詞注入的核心管線，但驗證時發現兩個遺留問題：

1. **切換 ASR 引擎後熱詞未重新注入**：`ASREngineRegistry.set_active_engine()` 卸載舊引擎、載入新引擎後，不會呼叫 `sync_hot_words()`。若用戶從 sherpa-onnx 切換至其他引擎（或反向），新引擎不會收到熱詞。
2. **Qwen3-ASR 引擎靜默忽略熱詞**：Qwen3-ASR（OpenVINO / PyTorch / Vulkan）的 `set_hot_words()` 為空實作，但 UI 不顯示任何提示，用戶不知道熱詞對當前引擎無效。

依賴：fix-hot-words（已完成）。

## What Changes

- **ASR 引擎切換時自動重新注入熱詞**：在 `set_active_engine()` 完成後觸發 callback，由 `__main__.py` 串接 `sync_hot_words()` 呼叫。
- **ASR 引擎回報熱詞支援能力**：在 ASREngine Protocol 新增 `supports_hot_words` 屬性，各引擎回報是否原生支援熱詞。
- **辭典 UI 顯示熱詞不支援提示**：當前使用的 ASR 引擎不支援熱詞時，辭典設定頁面頂部顯示警告標籤（如「目前引擎不支援熱詞偏置，建議改用替換規則」）。

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `asr-abstraction`：ASREngine Protocol 新增 `supports_hot_words: bool` 屬性；ASREngineRegistry 的 `set_active_engine()` 新增 `on_engine_changed` callback 機制。
- `dictionary-ui`：辭典設定頁面在引擎不支援熱詞時顯示警告標籤。

## Impact

- 受影響程式碼：
  - `airtype/core/asr_engine.py`（Protocol + Registry callback）
  - `airtype/core/asr_sherpa.py`（回報 `supports_hot_words = True`）
  - `airtype/core/asr_qwen_openvino.py`（回報 `supports_hot_words = False`）
  - `airtype/core/asr_qwen_pytorch.py`（回報 `supports_hot_words = False`）
  - `airtype/core/asr_qwen_vulkan.py`（回報 `supports_hot_words = False`）
  - `airtype/core/asr_breeze.py`（回報 `supports_hot_words = False`）
  - `airtype/ui/settings_dictionary.py`（警告標籤）
  - `airtype/__main__.py`（callback 串接）
- 無新依賴、無 API 變更、無破壞性變更
