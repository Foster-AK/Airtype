## Context

辭典引擎（Change 18-dictionary）已實作熱詞管理功能，包含 `DictionaryEngine.sync_hot_words()`、`SherpaOnnxEngine.set_hot_words()` 與 `_write_hotwords_file()` 等方法。但啟動流程（`__main__.py`）從未呼叫 `sync_hot_words()`，且 sherpa-onnx 的 Recognizer 建構也未傳遞 `hotwords_file` 參數，導致熱詞功能完全無效。

目前涉及的程式碼路徑：
- `airtype/__main__.py:163-169`：初始化 DictionaryEngine 但未注入熱詞
- `airtype/core/asr_sherpa.py:256-283`：`_build_offline_recognizer()` 未傳 `hotwords_file`
- `airtype/core/asr_sherpa.py:318-338`：`_write_hotwords_file()` 格式不含權重
- `airtype/core/dictionary.py:346-363`：`sync_hot_words()` 已實作但從未被呼叫

## Goals / Non-Goals

**Goals:**

- 讓 `sync_hot_words()` 在應用啟動時被呼叫，將啟用的熱詞注入 ASR 引擎
- 修復 sherpa-onnx 引擎的 hotwords_file 傳遞，使其原生熱詞功能真正生效
- 修正熱詞檔案格式以符合 sherpa-onnx 規範（`word :weight`）
- 確保設定面板修改辭典後能重新同步熱詞

**Non-Goals:**

- 不為 Qwen3-ASR 實作熱詞注入機制（模型架構不支援原生熱詞偏置）
- 不變更辭典引擎的資料模型或 JSON 格式
- 不變更辭典 UI 介面

## Decisions

### 啟動時注入熱詞

在 `__main__.py` 第 169 行（`dictionary_engine` 載入成功）之後，立即呼叫 `dictionary_engine.sync_hot_words(asr_engine)`。需在 `asr_engine is not None` 時才執行。

**理由**：此處是 DictionaryEngine 和 ASR 引擎都已就緒的最早時機，且 `sync_hot_words()` 已有完整實作，只需補上呼叫即可。

### sherpa-onnx hotwords_file 參數傳遞

修改 `_build_offline_recognizer()` 方法，在建構 `OfflineRecognizer` 時帶入 `hotwords_file=self._hotwords_file_path`。需判斷 `self._hotwords_file_path` 是否為 None，若為 None 則不傳（避免 sherpa-onnx 拋錯）。

使用 `**kwargs` 條件傳遞：
```python
hw_kwargs = {}
if self._hotwords_file_path:
    hw_kwargs["hotwords_file"] = self._hotwords_file_path
```

**理由**：SenseVoice 與 Paraformer 工廠方法都接受 `hotwords_file` 可選參數，但不確定所有版本都支援，使用條件傳遞較安全。

### 熱詞檔案格式修正

`_write_hotwords_file()` 中每行改為 `{word} :{weight}` 格式。`self._hot_words` 中的元素為 `HotWord(word, weight)` dataclass，可直接取用兩個屬性。

**理由**：sherpa-onnx hotwords 格式要求每行為 `詞語 :權重分數`，目前只寫了詞語缺少權重。

### 設定面板辭典變更後重新同步

檢查現有的設定面板 callback 機制。若 `SettingsWindow` 修改辭典後已觸發 `DictionaryEngine.save_set()` 並重載，需在該流程末端加入 `sync_hot_words()` 呼叫。若無現成 callback，則透過 `CoreController` 的事件機制通知重新同步。

## Risks / Trade-offs

- **[風險] sherpa-onnx 版本相容性**：某些舊版 sherpa-onnx 的 `from_sense_voice()` 可能不支援 `hotwords_file` 參數 → 使用 `try/except` 包裝，失敗時 log 警告並退回無熱詞模式。
- **[風險] Qwen 引擎用戶期望落差**：用戶使用 Qwen 引擎時熱詞仍無效 → 在 UI 或 log 中提示用戶改用替換規則作為替代方案。
- **[取捨] 不實作 Qwen prompt 注入**：雖然理論上可嘗試在 decoder prompt 中注入熱詞提示，但 Qwen3-ASR 架構未設計此機制，效果不確定且可能引入副作用，決定不做。
