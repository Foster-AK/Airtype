## Why

點擊設定視窗左側導覽列表時，Qt 預設焦點框（黑色虛線外框）會疊加在被選取的項目上，造成視覺突兀。原因是 `QListWidget` 的 QSS 缺少 `outline: 0`，導致平台預設焦點指示器顯示於 UI 上。

## What Changes

- 在 `airtype/ui/settings_window.py` 的 `_build_nav()` 方法中，於 `QListWidget` QSS 選擇器加入 `outline: 0`，移除焦點外框繪製
- 建立設定視窗導覽面板的正式規格（`settings-nav-panel`），記錄導覽列的視覺行為要求

## Capabilities

### New Capabilities

- `settings-nav-panel`: 設定視窗左側導覽面板的行為與視覺規格，包含項目選取樣式及焦點指示器抑制

### Modified Capabilities

(none)

## Impact

- Affected code: `airtype/ui/settings_window.py`
