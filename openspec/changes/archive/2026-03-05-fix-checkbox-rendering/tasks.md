## 1. 撰寫失敗測試（TDD）

- [x] 1.1 依「測試更新策略」，將 `tests/test_settings_dictionary.py` 中的 `test_checkbox_items_have_selectable_flag` 改寫為 `test_checkbox_items_use_qcheckbox_widget`，驗證「Checkbox Items Render Correctly on All Platforms」——熱詞 col 0、替換規則 col 0 和 col 3 的 `cellWidget` 含 `QCheckBox` 且勾選狀態與輸入資料一致

## 2. 新增輔助方法（`_make_check_widget` 與 `_get_cell_check`）

- [x] 2.1 [P] 在 `airtype/ui/settings_dictionary.py` import 區塊加入 `QCheckBox`，並在類別中新增 `_make_check_widget(self, checked, on_change) -> QWidget` 輔助方法（`_make_check_widget` 輔助方法設計），實現「以 `setCellWidget + QCheckBox` 取代 `QTableWidgetItem` checkstate」決策
- [x] 2.2 [P] 在 `airtype/ui/settings_dictionary.py` 新增 `_get_cell_check(self, table, row, col) -> bool` 輔助方法，從 `cellWidget` 讀取 `QCheckBox` 狀態，實現「`_get_cell_check` 輔助方法設計」決策

## 3. 修改 `_set_hw_row` 與 `_set_rr_row`

- [x] 3.1 [P] 修改 `_set_hw_row`（`airtype/ui/settings_dictionary.py`）：將 col 0 從 `QTableWidgetItem` checkstate 改為 `self._hw_table.setCellWidget(row, 0, self._make_check_widget(...))`，修復「Checkbox Items Render Correctly on All Platforms」enabled checkbox
- [x] 3.2 [P] 修改 `_set_rr_row`（`airtype/ui/settings_dictionary.py`）：將 col 0（enabled）與 col 3（regex）改為 `setCellWidget + _make_check_widget`，修復「Checkbox Items Render Correctly on All Platforms」regex checkbox

## 4. 更新 `_flush_hw_to_engine` 與 `_flush_rr_to_engine`

- [x] 4.1 [P] 修改 `_flush_hw_to_engine`（`airtype/ui/settings_dictionary.py`）：移除 `chk_item = table.item(row, 0)` 讀法，改用 `self._get_cell_check(self._hw_table, row, 0)`，確保「Checkbox state is readable after user interaction」
- [x] 4.2 [P] 修改 `_flush_rr_to_engine`（`airtype/ui/settings_dictionary.py`）：移除 `chk_item` 和 `regex_item` 的 item 讀法，改用 `_get_cell_check`，確保「Checkbox state is readable after user interaction」

## 5. 確認 `itemChanged` 信號相容性

- [x] 5.1 確認 `_on_hw_changed` / `_on_rr_changed`（`itemChanged` 信號，處理文字欄位）與新 `QCheckBox.stateChanged` 回呼並存無衝突，驗證「`itemChanged` 信號相容性」設計決策

## 6. 驗證

- [x] 5.1 執行 `pytest tests/test_settings_dictionary.py -v` 確認所有測試通過
- [x] 5.2 手動在深色主題下執行 `python -m airtype`，確認「Checkbox Items Render Correctly on All Platforms」——checked 顯示打勾（✓），unchecked 顯示空白方框
