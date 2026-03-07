## Context

Airtype 設定視窗（`settings_window.py`）採用左側 `QListWidget` 導覽面板 + 右側 `QStackedWidget` 內容區的二欄式佈局。

目前 `QListWidget` 的 QSS 僅定義了背景色、item padding 及選取狀態樣式，未抑制 Qt 平台預設的焦點框（focus rectangle）。當使用者以滑鼠點擊導覽項目時，Qt 在項目周圍繪製黑色虛線外框，與整體設計風格不符。

## Goals / Non-Goals

**Goals:**

- 移除 `QListWidget` 點擊後出現的黑色虛線焦點外框
- 保留選取狀態樣式（藍色背景 `#0a84ff` + 白色文字）不受影響

**Non-Goals:**

- 不修改任何其他 widget 的焦點樣式
- 不影響鍵盤導航功能（焦點框僅視覺上移除，Tab / 方向鍵仍可操作）

## Decisions

### Remove QListWidget Focus Outline via QSS `outline: 0`

在現有 QSS 字串的 `QListWidget { ... }` 選擇器中補入 `outline: 0;`。

**原因**：Qt 提供 `outline` CSS 屬性以控制焦點指示器，`outline: 0` 是跨平台的官方做法，不需要子類化或 `eventFilter`。改動範圍最小，僅一行 QSS 變更。

**替代方案考量**：
- 子類化 `QListWidget` 並覆寫 `drawFocus()` — 過度設計，不必要
- `setFocusPolicy(Qt.NoFocus)` — 會完全停用鍵盤焦點，影響可及性

## Risks / Trade-offs

- [低風險] Windows / macOS / Linux 對 `outline: 0` 的支援一致，無跨平台問題
