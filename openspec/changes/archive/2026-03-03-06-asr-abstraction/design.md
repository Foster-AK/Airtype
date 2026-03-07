## 背景

多個 ASR 引擎擁有不同的 API 與模型格式。統一的 Protocol 確保管線程式碼與引擎無關。

相依性：01-project-setup。

## 目標 / 非目標

**目標：**

- 透過 Python Protocol 定義標準 ASR 引擎契約
- 提供結果資料模型（ASRResult、PartialResult、HotWord）
- 以工廠模式實作引擎登錄檔，支援執行時切換

**非目標：**

- 不涉及實際 ASR 引擎實作（屬於 08、09、10）
- 不涉及模型載入或推理

## 決策

### 使用 Python Protocol 作為 ASR 引擎介面

使用 `typing.Protocol` 定義 ASR 引擎契約。方法：`load_model()`、`recognize()`、`recognize_stream()`、`set_hot_words()`、`set_context()`、`get_supported_languages()`、`unload()`。回傳 `ASRResult` dataclass。

**為何使用 Protocol 而非 ABC**：結構子型別（structural subtyping）——引擎不需要繼承基底類別。對第三方引擎外掛更為簡潔。

### 以工廠模式實作引擎登錄檔

`ASREngineRegistry` 將字串引擎 ID（例如 "qwen3-openvino"、"breeze-asr-25"）對應至工廠 callable。`get_engine(id)` 建立/回傳引擎實例。引擎於 import 時自行註冊。

### 透過 set_active_engine 實現執行時引擎切換

`set_active_engine(id)` 在載入新引擎前先卸載目前引擎。設定 `voice.asr_model` 決定啟動時的預設引擎。

## 風險 / 取捨

- [風險] 引擎載入時間各異（100ms–5s）→ 緩解措施：切換為非同步；UI 顯示載入狀態（由 13-core-controller 處理）
- [取捨] 工廠每次建立新實例 vs 快取 → 先以新實例保持簡單；若效能分析顯示需要再加入快取
