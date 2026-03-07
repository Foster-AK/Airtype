## 為什麼

Airtype 支援多個 ASR 引擎（Qwen3-ASR、Breeze-ASR-25、sherpa-onnx）。共用的抽象層讓管線能在不更改呼叫端程式碼的情況下切換引擎。這是所有 ASR 整合（08、09、10）的基礎。

參考：PRD §6.3.1（ASR 引擎抽象——Protocol 類別）。

相依性：01-project-setup。

## 變更內容

- 定義 `ASREngine` Protocol，包含標準介面（load_model、recognize、recognize_stream、set_hot_words、set_context、get_supported_languages、unload）
- 定義 `ASRResult` 與 `PartialResult` dataclass 作為辨識輸出
- 實作 `ASREngineRegistry` 用於引擎註冊與執行時切換
- 從設定 `voice.asr_model` 選擇預設引擎

## 功能

### 新增功能

- `asr-abstraction`：ASR 引擎 Protocol 介面、結果資料模型、引擎登錄檔，以及執行時引擎切換

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/asr_engine.py`、`tests/test_asr_engine.py`
- 無新增外部依賴（純 Python Protocol + dataclass）
- 相依：01-project-setup
