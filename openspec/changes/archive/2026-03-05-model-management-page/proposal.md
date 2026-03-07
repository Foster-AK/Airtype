## Why

目前 ASR 模型下載管理散落在語音設定頁（`settings_voice.py`），LLM 設定頁（`settings_llm.py`）則只有自由輸入路徑，未使用 manifest 驅動的模型清單。模型下載與設定選擇耦合在同一頁面，使用者無法一目了然地掌握所有可用模型的下載狀態，也無法方便地管理磁碟空間。需要一個獨立的「模型管理」頁面，以卡片式列表集中管理 ASR 與 LLM 模型的下載與刪除，並讓語音與 LLM 設定頁面簡化為只負責模型選擇。

## What Changes

- 新增獨立的「模型管理」設定頁面，以 QTabBar 區分 ASR / LLM 兩個分類，每個分類以可捲動的卡片式列表展示所有 manifest 中的模型
- 每張模型卡片顯示名稱、描述、檔案大小，並依下載狀態切換：未下載顯示「下載」按鈕、下載中顯示進度條與取消按鈕、已下載顯示綠勾與「刪除」按鈕
- 硬體建議模型旁標示「推薦」徽章（由 HardwareDetector 驅動）
- 下載在 QThread 背景執行，不阻塞 UI；同時間最多一個下載任務
- 支援刪除已下載模型（QMessageBox 確認後執行），釋放磁碟空間
- 設定視窗導覽列新增「模型管理」項目（插入於「語音/ASR」之後）
- 語音設定頁 ASR 模型下拉選單改為只列出已下載模型，移除下載指示符 `↓`
- LLM 設定頁本機模型從自由輸入路徑改為下拉選單（manifest 已下載模型 + 自訂路徑 fallback）
- ModelManager 新增 `delete_model()` 和 `get_model_path()` 方法
- 模型下載/刪除後透過 Signal 通知語音頁與 LLM 頁即時刷新下拉選單
- 四語系（zh_TW / zh_CN / en / ja）翻譯 key 擴充

## Capabilities

### New Capabilities

- `settings-models`: 模型管理設定頁面 — QTabBar 分類切換、卡片式模型列表、背景下載（QThread + 進度條）、模型刪除、跨頁面刷新 Signal

### Modified Capabilities

- `model-download`: 新增 `delete_model(model_id)` 和 `get_model_path(model_id)` 方法
- `settings-voice`: ASR 模型下拉選單改為只列出已下載模型，無模型時顯示提示
- `settings-nav-panel`: 新增「模型管理」導覽項目，分頁索引由 7 調整為 8

## Impact

- 新增檔案：`airtype/ui/settings_models.py`、`tests/test_settings_models.py`
- 修改檔案：`airtype/ui/settings_window.py`、`airtype/ui/settings_voice.py`、`airtype/ui/settings_llm.py`、`airtype/utils/model_manager.py`
- 修改 i18n 檔案：`locales/zh_TW.json`、`locales/zh_CN.json`、`locales/en.json`、`locales/ja.json`
- 分頁索引常數（`PAGE_*`）全面遞增，影響所有 `show_page()` 呼叫方
