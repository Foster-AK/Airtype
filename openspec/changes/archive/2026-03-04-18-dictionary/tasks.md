## 1. 辭典引擎

- [x] 1.1 建立 `airtype/core/dictionary.py` 實作熱詞管理：載入、儲存、透過 set_hot_words() 套用至 ASR 引擎 — 驗證：熱詞管理需求
- [x] 1.2 實作替換規則：字串比對與正規表達式模式，於 ASR 輸出後套用 — 驗證：替換規則需求
- [x] 1.3 實作辭典集，使用 JSON 儲存辭典檔案至 `~/.airtype/dictionaries/` — 驗證：辭典集需求、辭典檔案使用 JSON 儲存需求
- [x] 1.4 串接辭典引擎為管線後處理器（ASR 之後、LLM 之前）— 驗證：辭典引擎作為管線後處理器需求
  > **NOTE（來自 17-llm-polish 驗證）**：實作文字注入路徑時，需在 `controller.py` 中整合 `PolishPreviewDialog`（`airtype/ui/polish_preview.py`）：
  > 當 `config.llm.preview_before_inject is True` 時，文字注入前應先顯示對話框，讓使用者選擇原始或潤飾後版本，再呼叫 `TextInjector`。

## 2. 辭典 UI

- [x] 2.1 建立 `airtype/ui/settings_dictionary.py` 實作辭典 UI 可編輯表格元件：熱詞與替換規則設定頁面 — 驗證：辭典設定頁面需求
- [x] 2.2 實作辭典匯入與匯出（.txt/.csv/.json/.airtype-dict）— 驗證：辭典匯入與匯出需求

## 3. 測試

- [x] 3.1 撰寫熱詞單元測試（載入、儲存、套用至模擬引擎）
- [x] 3.2 撰寫替換規則單元測試（字串與正規表達式比對）
- [x] 3.3 撰寫辭典集切換單元測試
- [x] 3.4 撰寫匯入/匯出格式單元測試
