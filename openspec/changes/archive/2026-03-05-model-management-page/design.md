## Context

設定視窗目前有 7 個分頁（一般、語音/ASR、外觀、快捷鍵、LLM 潤飾、辭典、關於）。ASR 模型選擇嵌入語音設定頁，使用下拉選單列出所有 manifest 模型（包含未下載的，以 `↓` 標記）。LLM 設定頁的本機模型則是自由輸入路徑的 `QLineEdit`，完全沒有使用 manifest。

`ModelManager`（`airtype/utils/model_manager.py`）已提供 `list_models_by_category()`、`is_downloaded()`、`download()` 等 API，但只有下載功能，缺少刪除和路徑查詢。

manifest（`models/manifest.json`）包含 6 個 ASR 模型和 3 個 LLM 模型，每個條目有 `id`、`description`、`size_bytes`、`category`、`urls` 等欄位。

## Goals / Non-Goals

**Goals:**

- 新增獨立的「模型管理」設定頁面，以卡片式 UI 集中展示所有 ASR 與 LLM 模型的下載狀態
- 支援背景下載（QThread）與取消、模型刪除（含確認對話框）
- 簡化語音設定頁：ASR 下拉只列已下載模型
- 簡化 LLM 設定頁：本機模型改為下拉選單 + 自訂路徑 fallback
- 模型下載/刪除後跨頁面即時通知刷新

**Non-Goals:**

- 不實作模型的自動更新或版本管理
- 不支援並行下載多個模型（同時間最多一個）
- 不新增模型搜尋或篩選功能（模型數量少，卡片列表已足夠）
- 不改動 manifest 格式或 ModelManager 的下載邏輯

## Decisions

### 模型管理頁面分頁位置

將「模型管理」插入為設定視窗的第 3 個分頁（索引 2），位於「語音/ASR」之後。理由：使用者在語音頁看到模型選擇後，最自然的下一步就是管理模型下載。分頁索引常數（`PAGE_*`）全面遞增，`PAGE_MODELS = 2`，後續頁面各 +1。

替代方案：放在「關於」之前（索引 6）。但模型管理是高頻操作，不應藏在最後。

### 模型卡片 UI 結構

每張模型卡片為 `QFrame` 搭配圓角邊框（`border-radius: 8px`），內部 `QHBoxLayout` 分為左側文字區（名稱 + 推薦徽章 + 描述 + 檔案大小）和右側動作區（fixedWidth ~120）。三種互斥狀態以 `setVisible()` 切換：

1. **未下載**：顯示「下載」QPushButton
2. **下載中**：顯示 QProgressBar + 百分比 QLabel + 「取消」QPushButton
3. **已下載**：顯示綠色 ✓ QLabel + 「刪除」QPushButton

替代方案：使用 QListWidget + 自訂 delegate。但 QFrame 組合更靈活，可精確控制每個 widget 的佈局與動畫。

### 分類切換機制

使用 QTabBar（非 QTabWidget），搭配手動管理 QScrollArea 內的卡片列表。切換 tab 時清空 `_cards_layout` 並重建對應類別的卡片。

替代方案：使用 QTabWidget 預建兩個頁面。但 QTabBar 更輕量，且卡片需動態更新下載狀態，統一管理更簡潔。

### 下載執行緒設計

使用 `DownloadWorker(QThread)` 封裝 `ModelManager.download()` 呼叫。透過 progress callback 在每個 chunk（1 MB）後發射 Signal 更新 UI。取消機制：設置 `_cancelled` flag，callback 中檢測後拋出例外中斷 httpx 迴圈。

同時間限制一個下載任務：`SettingsModelsPage` 維護 `_active_worker: Optional[DownloadWorker]`，有下載進行時其餘卡片的下載按鈕 disable。

### LLM 本機模型下拉 + 自訂路徑

將 `QLineEdit` 替換為 `QComboBox`，列出 manifest 已下載的 LLM 模型，最後附加「自訂路徑…」選項。選擇自訂路徑時顯示 `QLineEdit` 讓使用者輸入。向後相容：若 config 中的 `local_model` 不匹配任何 manifest model_id，自動選中「自訂路徑」並填入路徑值。

### 跨頁面刷新 Signal

`SettingsModelsPage` 發射 `model_downloaded(str)` 和 `model_deleted(str)` Signal。`SettingsWindow` 在 `_add_pages()` 中連接至 `_on_model_state_changed()`，呼叫 `_page_voice.refresh_asr_combo()` 和 `_page_llm.refresh_llm_combo()`。

### 卡片主題適配

卡片 QSS 區分淺色/深色兩套樣式（邊框色、背景色、hover 色）。`SettingsModelsPage` 監聽 `appearance.theme` 變更，在 `_apply_card_theme()` 中更新所有卡片的 stylesheet。

## Risks / Trade-offs

- **[分頁索引遞增]** → 所有外部透過 `PAGE_*` 常數引用的呼叫方需同步更新。透過 grep 確認所有 `show_page()` 和 `PAGE_` 常數引用。
- **[LLM local_model 格式變更]** → 舊版 config 中的 `local_model` 可能是檔案路徑而非 model_id。以向後相容邏輯處理：不匹配 manifest 時 fallback 到自訂路徑。
- **[下載中關閉視窗]** → 使用者可能在下載進行中關閉設定視窗。在 `SettingsWindow.closeEvent()` 中檢查 active worker，若有則提示使用者等待或取消。
- **[刪除正在使用的模型]** → 刪除前檢查 `config.voice.asr_model` 和 `config.llm.local_model`，若匹配則先警告使用者。
