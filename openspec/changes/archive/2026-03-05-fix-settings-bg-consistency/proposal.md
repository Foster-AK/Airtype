## Why

設定視窗右側內容區（`QStackedWidget`）沒有設定明確背景色，在 Windows 11 上繼承系統預設的暖米/卡其色，與左側導覽列的冷灰（`#f0f0f0`）形成顯著色差，造成視覺突兀與不一致感。

## What Changes

- 在 `_build_ui()` 中以一個有明確背景色的 `QWidget`（`_content_bg`）包裝 `QStackedWidget`，使右側內容區顯示一致的 `#ffffff`（淺色/系統主題）或 `#2d2d2d`（深色主題）
- 新增 `_apply_content_bg(theme)` 實例方法，同步更新導覽列（`#fafafa`／`#252525`）與內容區背景色
- 在 `__init__` 結尾呼叫 `_apply_content_bg()` 並連接 `theme_changed` 信號，使主題切換即時生效
- 改善導覽列 QSS：加入 `margin` 實現內縮 pill 選取樣式、補上 hover 狀態

## Capabilities

### New Capabilities

- `settings-window-theme`: 設定視窗整體主題感知背景色管理，確保導覽列與內容區在淺色、系統、深色三種主題下均呈現一致的顏色

### Modified Capabilities

- `settings-nav-panel`: 導覽列項目選取樣式由全寬填滿改為內縮 pill（`margin: 2px 8px`），新增 hover 反饋狀態

## Impact

- Affected code: `airtype/ui/settings_window.py`, `tests/test_settings_window.py`
