## 1. 設定框架

- [x] 1.1 建立 `airtype/ui/settings_window.py` 實作 QStackedWidget 分頁內容切換：左側 QListWidget 導覽 + 右側內容區域 — 驗證：QStackedWidget 分頁內容切換需求
- [x] 1.2 實作 widget 變更時自動儲存，含 500ms 防抖動 — 驗證：widget 變更時自動儲存需求

## 2. 設定頁面

- [x] 2.1 建立 `airtype/ui/settings_general.py` 實作一般設定頁面控制項 — 驗證：一般設定頁面需求
- [x] 2.2 建立 `airtype/ui/settings_voice.py` 實作語音設定頁面控制項 — 驗證：語音設定頁面需求
- [x] 2.3 建立 `airtype/ui/settings_appearance.py` 實作外觀設定頁面控制項 — 驗證：外觀設定頁面需求
- [x] 2.4 建立 `airtype/ui/settings_shortcuts.py` 實作透過按鍵事件擷取的快捷鍵錄製與衝突偵測 — 驗證：快捷鍵設定頁面需求
- [x] 2.5 建立 `airtype/ui/settings_about.py` 實作關於頁面：版本、系統資訊、更新檢查、匯出診斷資料 — 驗證：關於頁面需求

## 3. 測試

- [x] 3.1 撰寫設定視窗的單元測試（分頁切換、自動儲存）
- [x] 3.2 撰寫快捷鍵錄製器的單元測試（按鍵擷取、衝突偵測）
