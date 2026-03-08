## 1. ASR Engine Protocol 新增 supports_hot_words 屬性

- [x] [P] 1.1 修改 ASR Engine Protocol：在 `airtype/core/asr_engine.py` 新增 `supports_hot_words: bool` 屬性
- [x] [P] 1.2 在 `airtype/core/asr_sherpa.py` 的 SherpaOnnxEngine 新增 `supports_hot_words` property 回傳 `True`
- [x] [P] 1.3 在 `airtype/core/asr_qwen_openvino.py` 新增 `supports_hot_words` property 回傳 `False`
- [x] [P] 1.4 在 `airtype/core/asr_qwen_pytorch.py` 新增 `supports_hot_words` property 回傳 `False`
- [x] [P] 1.5 在 `airtype/core/asr_qwen_vulkan.py` 新增 `supports_hot_words` property 回傳 `False`
- [x] [P] 1.6 在 `airtype/core/asr_breeze.py` 新增 `supports_hot_words` property 回傳 `False`

## 2. ASREngineRegistry 引擎切換 callback

- [x] 2.1 在 `airtype/core/asr_engine.py` 的 ASREngineRegistry 新增 `on_engine_changed: Optional[Callable[[str], None]]` 屬性（初始為 None）
- [x] 2.2 修改 Runtime Engine Switching：在 `set_active_engine()` 方法結尾，切換完成後呼叫 `on_engine_changed(engine_id)`（若非 None）
- [x] 2.3 在 `airtype/__main__.py` 初始化後設定 `asr_registry.on_engine_changed` callback，呼叫 `sync_hot_words()` 重新注入熱詞

## 3. 辭典 UI 警告標籤（Hot Words Engine Support Warning）

- [x] 3.1 在 `airtype/ui/settings_dictionary.py` 的 `SettingsDictionaryPage.__init__()` 新增 `asr_registry` 可選參數
- [x] 3.2 實作 Hot Words Engine Support Warning：在熱詞區塊頂部新增 `QLabel` 警告標籤，文字使用 i18n key
- [x] 3.3 新增 `_update_hw_warning()` 方法：查詢 `asr_registry.active_engine.supports_hot_words`，控制警告標籤顯示/隱藏
- [x] 3.4 在 `airtype/ui/settings_window.py` 傳遞 `asr_registry` 參數至 SettingsDictionaryPage
- [x] 3.5 在 `airtype/__main__.py` 的 `on_engine_changed` callback 中同時觸發辭典 UI 更新警告標籤

## 4. 測試

- [x] [P] 4.1 新增測試：驗證 `SherpaOnnxEngine.supports_hot_words` 回傳 `True`
- [x] [P] 4.2 新增測試：驗證 Qwen3-ASR 各引擎 `supports_hot_words` 回傳 `False`
- [x] [P] 4.3 新增測試：驗證 `set_active_engine()` 呼叫 `on_engine_changed` callback
- [x] 4.4 執行 `python -m pytest tests/ -v --tb=short` 確認所有測試通過
