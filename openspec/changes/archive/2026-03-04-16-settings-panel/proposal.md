## 為什麼

使用者需要一個完整的設定介面，以配置 Airtype 的所有面向：一般偏好設定、ASR 模型選擇、外觀、快捷鍵，以及系統資訊。設定面板是一個獨立的分頁式視窗。

參考：PRD §5.1-5.8（設定面板 — 所有分頁）。

相依性：13-core-controller、14-overlay-ui。

## 變更內容

- 實作設定視窗框架，含左側導覽 + 右側內容區域
- 實作 5 個設定頁面：一般、語音/ASR、外觀、快捷鍵、關於
- 所有變更自動儲存至 config
- 快捷鍵錄製 UI，含衝突偵測

## 功能

### 新增功能

- `settings-general`：一般設定頁面（語言、自動啟動、靜音逾時、通知）
- `settings-voice`：語音/ASR 設定頁面（裝置、模型選擇、辨識模式）
- `settings-appearance`：外觀設定頁面（主題、膠囊位置、縮放比例、波形樣式）
- `settings-shortcuts`：快捷鍵設定頁面（按鍵錄製、衝突偵測）
- `settings-about`：關於頁面（版本、系統資訊、模型資訊、更新檢查）

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/ui/settings_window.py`、`airtype/ui/settings_general.py`、`airtype/ui/settings_voice.py`、`airtype/ui/settings_appearance.py`、`airtype/ui/settings_shortcuts.py`、`airtype/ui/settings_about.py`
- 相依於：13-core-controller、14-overlay-ui
