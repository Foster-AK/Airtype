## 1. 重構 _build_ui() 佈局

- [x] 1.1 在 `_build_ui()` 中，移除 `QSplitter` 及其相關呼叫（`setStretchFactor`），改以「以 QHBoxLayout 取代 QSplitter」方案：建立 `QHBoxLayout`，以 `addWidget(left, stretch=0)` 加入左側，以 `addWidget(right, stretch=1)` 加入右側，確保 Dictionary Page Layout Uses QHBoxLayout

## 2. 重構 _build_sets_panel()

- [x] 2.1 將 `_build_sets_panel()` 的回傳型別從 `QWidget` 改為 `QGroupBox`（標題 `tr("settings.dictionary.sets_label")`），移除原本的 bold `QLabel` 標題，套用「左側辭典集改為 QGroupBox」決策，確保 Dictionary Set Panel Uses QGroupBox

## 3. 清理與同步

- [x] 3.1 確認 `retranslate_ui()` 中的標題更新邏輯改為更新 `QGroupBox` 標題（`setTitle()`），移除原 `self._sets_lbl` 的 `setText()` 呼叫
- [x] 3.2 移除 `QSplitter` 相關 import（若 `QSplitter` 已無其他用途）

## 4. 驗證

- [x] 4.1 手動執行設定面板，切換至辭典頁籤，確認三個 QGroupBox（辭典集、熱詞、替換規則）並列顯示，無空白間距
