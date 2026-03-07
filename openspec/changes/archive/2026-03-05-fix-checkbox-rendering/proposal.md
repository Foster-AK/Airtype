## Problem

辭典設定頁面（`SettingsDictionaryPage`）的熱詞與替換規則表格中，「啟用」與「正規表達式」欄位的 checkbox 在深色主題下渲染異常：
- **Checked（True）狀態**：顯示純黑色方框，無打勾符號（✓）
- **Unchecked（False）狀態**：方框消失，完全不可見

前一個修復嘗試（`fix-dictionary-ui-bugs`：加入 `Qt.ItemFlag.ItemIsSelectable`）無效，問題仍然存在。

## Root Cause

`QTableWidgetItem` 的 checkbox indicator 由 Qt style engine 的 `QStyle::PE_IndicatorViewItemCheck` 繪製，其顏色取自 `QPalette`。應用程式啟用深色主題時：

- `_DARK_STYLESHEET`（`settings_window.py`）設定 `QTableWidget` 背景為 `#2d2d2d`
- `_dark_palette()` 將 `QPalette.Text` 設為 `#dcdcdc`（淺色），但 checkbox indicator 繪製邏輯在 Windows Fusion/Vista style 下使用不同的 role
- 結果：indicator 以深色繪製於深色背景，造成黑框或消失

`ItemIsSelectable` 無法改變 `PE_IndicatorViewItemCheck` 的顏色路徑，因此修復無效。

## Proposed Solution

將 checkbox 欄位（`_set_hw_row` col 0、`_set_rr_row` col 0 和 col 3）從 `QTableWidgetItem` checkstate 方案改為 `setCellWidget()` 注入真正的 `QCheckBox` widget。

`QCheckBox` 使用 `QStyle::PE_IndicatorCheckBox`（非 view item 路徑）以 OS native 方式渲染，不受 `QAbstractItemView` 的主題色彩影響，在深色與淺色主題下均能正確顯示打勾與空框。

新增兩個私有輔助方法：
- `_make_check_widget(checked, on_change) -> QWidget`：建立含置中 `QCheckBox` 的容器，`stateChanged` 連接 `on_change` 回呼
- `_get_cell_check(table, row, col) -> bool`：從 cellWidget 讀取 `QCheckBox` 的勾選狀態，取代原有 `item.checkState()` 讀法

## Success Criteria

- 熱詞的「啟用」checkbox 在深色主題下 Checked 顯示打勾（✓），Unchecked 顯示空白方框
- 替換規則的「啟用」與「正規表達式」checkbox 同上
- 淺色主題下行為不受影響
- `_flush_hw_to_engine` 與 `_flush_rr_to_engine` 正確讀取新 widget 狀態
- 現有測試更新後通過，新測試驗證 cellWidget 含 `QCheckBox`

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dictionary-ui`: 修正 checkbox 欄位在深色主題下渲染異常的問題，改用 `setCellWidget + QCheckBox` 取代 `QTableWidgetItem` checkstate 方案

## Impact

- Affected code: `airtype/ui/settings_dictionary.py`, `tests/test_settings_dictionary.py`
