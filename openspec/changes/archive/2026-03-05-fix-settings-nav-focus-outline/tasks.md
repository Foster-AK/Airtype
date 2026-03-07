## 1. 測試先行（TDD）

- [x] 1.1 撰寫測試：驗證 `QListWidget` Navigation Panel Focus Indicator — QSS 包含 `outline: 0` 且不含焦點外框設定
- [x] 1.2 撰寫測試：驗證 Navigation Panel Selection Style — 選取項目的 QSS 包含 `background: #0a84ff` 和 `color: white`

## 2. 實作修正

- [x] 2.1 在 `settings_window.py` `_build_nav()` 的 `QListWidget` QSS 選擇器中套用 Remove QListWidget Focus Outline via QSS `outline: 0`

## 3. 驗證

- [x] 3.1 執行單元測試，確認 1.1 與 1.2 測試通過
- [x] 3.2 手動啟動設定視窗，點擊各導覽分頁確認黑色焦點外框消失，選取樣式維持正常
