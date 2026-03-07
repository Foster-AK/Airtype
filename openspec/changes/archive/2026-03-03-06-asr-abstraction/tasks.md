## 1. Protocol 與資料模型

- [x] 1.1 建立 `airtype/core/asr_engine.py`，以 Python Protocol 定義 ASR 引擎介面：定義 `ASREngine` Protocol，包含所有方法（load_model、recognize、recognize_stream、set_hot_words、set_context、get_supported_languages、unload）— 驗證：ASR 引擎 Protocol 需求
- [x] 1.2 實作 ASR 結果資料模型：`ASRResult` dataclass（text、language、confidence、segments）與 `PartialResult` dataclass（text、is_final）— 驗證：ASR 結果資料模型需求
- [x] 1.3 實作 `HotWord` dataclass（word: str, weight: int）

## 2. 引擎登錄檔

- [x] 2.1 以工廠模式實作引擎登錄檔：`ASREngineRegistry` 搭配 `register_engine(id, factory)` 與 `get_engine(id)` — 驗證：引擎登錄檔需求
- [x] 2.2 透過 set_active_engine 實作執行時引擎切換：`set_active_engine(id)` 搭配卸載/載入週期 — 驗證：執行時引擎切換需求
- [x] 2.3 實作從設定載入預設引擎：啟動時載入 `voice.asr_model` 指定的引擎 — 驗證：從設定載入預設引擎需求

## 3. 測試

- [x] 3.1 撰寫實作 Protocol 的 mock ASR 引擎供測試使用
- [x] 3.2 登錄檔的單元測試（註冊、取得、切換、未知引擎錯誤）
- [x] 3.3 ASRResult 與 PartialResult 資料模型的單元測試
