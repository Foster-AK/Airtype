## Problem

辭典設定頁面（`SettingsDictionaryPage`）存在兩個回歸問題：
1. 使用者點擊 ＋ 新增辭典集後，清單不更新、新辭典集不出現。
2. 熱詞與替換規則表格中的 Checkbox，在啟用狀態（True）下顯示為實心黑色方塊，而非正常打勾（✓）的 checkbox 外觀；停用狀態（False）時方塊消失。

## Root Cause

**Bug 1 — 辭典集無法新增（雙重根因）：**

- **情況 A（`_dict_engine is None`）**：`_on_add_set` 的 `if self._dict_engine is not None:` 區塊被靜默略過，新名稱從未存入任何資料結構，之後的 `_reload_sets_list()` 讀取舊資料，使用者看不到任何回饋。
- **情況 B（`_dict_engine is not None`）**：`create_set()` / `save_set()` 雖然成功，但 `_on_add_set` 未更新 `self._current_set` 並未呼叫 `_load_set_data(name)`，UI 選取停留在舊辭典集，使用者誤以為新增失敗。

**Bug 2 — Checkbox 黑色方塊：**

`_set_hw_row` 及 `_set_rr_row` 建立 `QTableWidgetItem` 時只設定了 `ItemIsUserCheckable | ItemIsEnabled`，遺漏 `ItemIsSelectable`。Windows 的 PySide6 style engine 需要 `ItemIsSelectable` 才能正確繪製 checkbox indicator，缺少時 fallback 為填滿的黑色矩形。

## Proposed Solution

- **`_on_add_set`**：
  - 情況 A：當 `_dict_engine is None` 時顯示警告對話框（明確錯誤提示），不再靜默失敗。
  - 情況 B：成功建立後，設定 `self._current_set = name`，呼叫 `_reload_sets_list()` 再呼叫 `_load_set_data(name)`，讓 UI 自動切換至新辭典集。
- **`_set_hw_row` / `_set_rr_row`**：所有 checkbox `QTableWidgetItem` 的 flags 加入 `Qt.ItemFlag.ItemIsSelectable`，修復三處（enabled×2、regex×1）。

## Success Criteria

- 新增辭典集後，清單立即顯示新辭典集且自動選取切換。
- `_dict_engine is None` 時顯示警告，不靜默失敗。
- 熱詞與替換規則的 enabled checkbox 在 Checked 狀態下顯示打勾（✓），Unchecked 狀態下顯示空白方框。
- regex checkbox 亦同。
- 現有單元測試與整合測試通過。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dictionary-ui`: 修正辭典集新增後 UI 不更新、及 Checkbox 在 Windows 上渲染異常的行為，使實作與現有規格的 Scenario 一致。

## Impact

- Affected code: `airtype/ui/settings_dictionary.py`
