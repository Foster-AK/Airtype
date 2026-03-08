## 1. 修復啟動時注入熱詞（Application Entry Point Component Wiring）

- [x] [P] 1.1 修正 Application Entry Point Component Wiring：在 `airtype/__main__.py` 第 169 行後加入 `dictionary_engine.sync_hot_words(asr_engine)` 呼叫，需判斷 `dictionary_engine is not None and asr_engine is not None`
- [x] 1.2 驗證：啟動應用後，log 中出現「已套用 N 個熱詞至 ASR 引擎」訊息

## 2. 修復 sherpa-onnx Hot Words 傳遞

- [x] [P] 2.1 修正 sherpa-onnx Hot Words：修改 `airtype/core/asr_sherpa.py` 的 `_build_offline_recognizer()`，在 `from_sense_voice()` 和 `from_paraformer()` 呼叫中條件傳入 `hotwords_file=self._hotwords_file_path`（僅當非 None 時）
- [x] [P] 2.2 熱詞檔案格式修正：修正 `_write_hotwords_file()` 格式，每行改為 `{word} :{weight}`（sherpa-onnx hotwords_file 格式）
- [x] 2.3 驗證：呼叫 `set_hot_words()` 後檢查臨時檔案內容包含正確的 `word :weight` 格式
- [x] 2.4 在 `_build_offline_recognizer()` 中加入 `try/except` 包裝 `hotwords_file` 傳遞，失敗時 log 警告並退回無熱詞模式（sherpa-onnx 版本相容性，對應設計中「sherpa-onnx hotwords_file 參數傳遞」決策）

## 3. Recognizer 重建與動態同步（設定面板辭典變更後重新同步）

- [x] 3.1 確認 `_rebuild_offline_recognizer()` 在 `set_hot_words()` 後正確重建 Recognizer 並帶入新的 `hotwords_file`
- [x] 3.2 檢查設定面板辭典儲存流程，確保辭典變更後觸發 `sync_hot_words(asr_engine)` 重新注入

## 4. 測試

- [x] [P] 4.1 新增或更新 `tests/test_asr_sherpa.py` 中的測試：驗證 `_write_hotwords_file()` 產生正確格式（`word :weight`）
- [x] [P] 4.2 新增或更新 `tests/test_dictionary.py` 中的測試：驗證 `sync_hot_words()` 被呼叫時正確傳遞啟用的熱詞
- [x] 4.3 執行 `python -m pytest tests/test_dictionary.py tests/test_asr_sherpa.py -v` 確認所有測試通過
