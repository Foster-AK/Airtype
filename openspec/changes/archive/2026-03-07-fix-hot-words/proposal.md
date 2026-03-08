## Why

辭典引擎的熱詞（Hot Words）功能目前完全無效。用戶在辭典中加入熱詞（如「龔玉惠」權重 7），但 ASR 引擎仍辨識為同音錯字（「公寓會」）。根本原因有三層斷裂：

1. **主程式從未呼叫 `sync_hot_words()`**：`__main__.py` 初始化 `DictionaryEngine` 後未將熱詞注入 ASR 引擎。
2. **sherpa-onnx 建構 Recognizer 時未傳 `hotwords_file` 參數**：即使呼叫 `set_hot_words()`，`_build_offline_recognizer()` 也不會把熱詞檔案傳給 sherpa-onnx。
3. **熱詞檔案格式缺少權重**：`_write_hotwords_file()` 只寫詞語，缺少 sherpa-onnx 要求的 `:weight` 格式。

此 bug 使得 Change 18-dictionary 中設計的熱詞功能形同虛設，需立即修復。

## What Changes

- **修復主程式熱詞注入**：在 `__main__.py` 的 `DictionaryEngine` 初始化後呼叫 `sync_hot_words(asr_engine)`，確保啟動時熱詞即注入 ASR 引擎。
- **修復 sherpa-onnx hotwords_file 傳遞**：在 `asr_sherpa.py` 的 `_build_offline_recognizer()` 中，將 `self._hotwords_file_path` 傳入 `from_sense_voice()` / `from_paraformer()` 工廠方法。
- **修正熱詞檔案格式**：`_write_hotwords_file()` 改為寫入 `word :weight` 格式，符合 sherpa-onnx hotwords 規範。
- **確保設定面板變更後重新同步熱詞**：當用戶修改辭典後，觸發 `sync_hot_words()` 重新注入。

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `main-wiring`：啟動流程需在辭典引擎初始化後呼叫 `sync_hot_words(asr_engine)` 注入熱詞。
- `asr-sherpa`：`_build_offline_recognizer()` 需傳遞 `hotwords_file` 參數；`_write_hotwords_file()` 需產生正確的權重格式。

## Impact

- 受影響程式碼：
  - `airtype/__main__.py`（啟動流程）
  - `airtype/core/asr_sherpa.py`（Recognizer 建構 + 熱詞檔案寫入）
- 受影響 specs：`main-wiring`、`asr-sherpa`
- 無新依賴、無 API 變更、無破壞性變更
