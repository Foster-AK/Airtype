## Context

`SettingsWindow` 的 `_build_ui()` 目前將 `QStackedWidget` 直接加入根佈局，沒有明確設定背景色。在 Windows 11 上，`QApplication.style().standardPalette()` 的 `Window` 色角帶有暖米/卡其調，使右側內容區與左側明確設定為 `#f0f0f0` 的導覽列產生色差。深色主題已有 `_dark_palette()` 處理，但 `_build_ui()` 中的 QSS 層並未隨主題更新，造成視覺不一致。

## Goals / Non-Goals

**Goals:**

- 使設定視窗在淺色（light）、系統（system）、深色（dark）三種主題下，導覽列與內容區均呈現一致的明確背景色
- 主題切換時即時更新背景，無需重開視窗
- 同步改善導覽列項目選取樣式（內縮 pill + hover）

**Non-Goals:**

- 不修改各設定子頁面（`SettingsGeneralPage` 等）內部的背景樣式
- 不引入新的第三方相依套件
- 不改變現有的 `apply_theme()` 全域 QPalette 機制

## Decisions

### 以 QSS objectName 選取器控制內容區背景

在 `_build_ui()` 中以 `QWidget`（命名為 `contentBg`）包裝 `QStackedWidget`，並以 `#contentBg { background-color: ... }` QSS 選取器設定背景。

此方式優先於直接呼叫 `setPalette()`，因為 QSS 選取器只影響指定物件，不會意外覆蓋子 widget 的樣式；同時比全域 QPalette 更易局部控制。

替代方案：修改 `apply_theme()` 在應用程式層改變 Window palette 顏色 → 會影響所有視窗，副作用範圍過大，故不採用。

### 新增 `_apply_content_bg(theme)` 實例方法

將導覽列（`self._nav_widget`）與內容區（`self._content_bg`）的背景更新集中於單一方法，由 `__init__` 初始化呼叫，並由 `theme_changed` 信號觸發，確保主題切換時兩者同步更新。

色彩規格：

| 主題 | 導覽列 | 內容區 |
|------|--------|--------|
| light / system | `#fafafa` | `#ffffff` |
| dark | `#252525` | `#2d2d2d` |

### 導覽列 QSS 改用內縮 pill 樣式

在 `QListWidget::item` 加入 `margin: 2px 8px`，使 `border-radius: 6px` 正確顯示為圓角區塊，同時補上 `QListWidget::item:hover:!selected` hover 反饋，提升互動品質。

## Risks / Trade-offs

- [風險] `#contentBg` QSS 選取器在主題切換後可能被全域 QPalette 蓋過 → 在 `_apply_content_bg()` 中主動呼叫 `setStyleSheet()` 可確保 QSS 優先；Qt 的 QSS 優先級高於 QPalette，無需額外處理
- [風險] 「系統」主題在不同 OS 上的 palette 顏色不同，我們明確覆蓋可能與 OS 主題期望不符 → 此為刻意決策；Airtype 設定視窗使用固定色系以保持品牌一致性，「系統」主題在視窗內部行為與「淺色」相同
