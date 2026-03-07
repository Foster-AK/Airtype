## Context

`SettingsDictionaryPage`（`airtype/ui/settings_dictionary.py`）使用 `QTableWidget` 呈現熱詞與替換規則。checkbox 欄位目前以 `QTableWidgetItem` + `Qt.ItemFlag.ItemIsUserCheckable` 實作，其 indicator 由 `QStyle::PE_IndicatorViewItemCheck` 繪製。

應用程式套用 `_dark_palette()` 與 `_DARK_STYLESHEET` 後，`QTableWidget` 的背景為 `#2d2d2d`，而 `PE_IndicatorViewItemCheck` 所使用的顏色在 Windows Fusion/Vista style 下與背景相近，導致 checkbox indicator 不可見或顯示為實心黑框。

前一次修復嘗試（加入 `ItemIsSelectable`）確認無效，因為該 flag 不改變 `PE_IndicatorViewItemCheck` 的顏色路徑。

## Goals / Non-Goals

**Goals:**

- 將 checkbox 欄位改為 `setCellWidget()` + `QCheckBox` widget，使用 OS native 渲染路徑（`PE_IndicatorCheckBox`），不受 view item style 的主題色影響
- 提供 `_make_check_widget` 與 `_get_cell_check` 兩個私有輔助方法，保持程式碼乾淨
- 保持資料讀寫語意不變（`_flush_hw_to_engine` / `_flush_rr_to_engine` 仍正確收集狀態）
- 更新對應測試以驗證新的 widget 方案

**Non-Goals:**

- 修改主題系統（`settings_window.py`）
- 修改 `DictionaryEngine`
- 變更表格的整體佈局或欄位定義

## Decisions

### 以 `setCellWidget + QCheckBox` 取代 `QTableWidgetItem` checkstate

**問題核心**：`QTableWidgetItem` 的 checkbox 使用 `QStyle::PE_IndicatorViewItemCheck`，此路徑的顏色受 `QAbstractItemView` 的 palette 影響，在自訂深色 palette 下顯示異常。

**決策**：改用 `setCellWidget()` 注入一個含置中 `QCheckBox` 的容器 widget。`QCheckBox` 走 `QStyle::PE_IndicatorCheckBox` 路徑，此路徑使用 OS native 系統控制項渲染，正確繼承深色/淺色主題。

影響的欄位：

| 方法 | 欄位 | 說明 |
|------|------|------|
| `_set_hw_row` | col 0 | 熱詞啟用 |
| `_set_rr_row` | col 0 | 替換規則啟用 |
| `_set_rr_row` | col 3 | 替換規則正規表達式 |

### `_make_check_widget` 輔助方法設計

```python
def _make_check_widget(self, checked: bool, on_change) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cb = QCheckBox()
    cb.blockSignals(True)
    cb.setChecked(checked)
    cb.blockSignals(False)
    cb.stateChanged.connect(on_change)
    layout.addWidget(cb)
    return container
```

`cb.blockSignals(True/False)` 包圍 `setChecked()` 的關鍵設計：防止初始化時觸發 `on_change` 回呼。呼叫端（`_populate_hw_table` 等）已用 `table.blockSignals(True)` 包圍，但 table 的 blockSignals 不阻斷 cellWidget 內的信號，因此 QCheckBox 層級的保護是必要的。

`on_change` 回呼由呼叫端傳入（lambda），分別對應 hw 或 rr 的 flush + save 操作：
- hw: `lambda: (self._flush_hw_to_engine(), self._trigger_save())`
- rr: `lambda: (self._flush_rr_to_engine(), self._trigger_save())`

### `_get_cell_check` 輔助方法設計

```python
def _get_cell_check(self, table: "QTableWidget", row: int, col: int) -> bool:
    widget = table.cellWidget(row, col)
    if widget is None:
        return True
    cb = widget.findChild(QCheckBox)
    return cb.isChecked() if cb else True
```

`findChild(QCheckBox)` 在容器 widget 內找到 `QCheckBox` 實例，讀取其 `isChecked()` 狀態，取代原有的 `item.checkState() == Qt.CheckState.Checked`。

### `itemChanged` 信號相容性

原有 `_on_hw_changed` / `_on_rr_changed` 連接 `itemChanged` 信號，處理文字欄位（詞彙、權重、原始文字、替換文字）的變更。cellWidget 的 `QCheckBox` 不觸發 `itemChanged`，而是透過 `stateChanged → on_change` 直接呼叫 flush/save。兩個機制並存，互不干擾。

### 測試更新策略

原有 `test_checkbox_items_have_selectable_flag` 驗證 `QTableWidgetItem` 的 flags，在新方案下該 item 不存在（`table.item(row, 0)` 回傳 `None`）。需將測試改為：

1. 驗證 `cellWidget(row, col)` 不為 None
2. 驗證其中含有 `QCheckBox`（`findChild(QCheckBox) is not None`）
3. 驗證 `QCheckBox.isChecked()` 與輸入資料一致

## Risks / Trade-offs

- [Risk] `setCellWidget` 之後，表格選取整行時 checkbox 欄位顯示為 widget 而非 item，視覺行為略有不同（widget 不隨 row highlight 反白） → Mitigation：這是 Qt 預期行為，checkbox 仍可操作，不影響功能或使用者體驗
- [Risk] `_make_check_widget` 中的 lambda `on_change` 在 Python closure 規則下可能捕捉錯誤的變數 → Mitigation：lambda 只呼叫 `self` 方法，無 loop 變數捕捉問題，安全
- [Risk] `findChild(QCheckBox)` 若容器結構變動會靜默回傳 None → Mitigation：`_get_cell_check` 有 `if cb else True` 防衛，且結構由 `_make_check_widget` 完全控制
