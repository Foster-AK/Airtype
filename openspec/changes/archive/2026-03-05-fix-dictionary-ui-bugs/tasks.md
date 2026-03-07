## 1. 撰寫失敗測試（TDD）

- [x] 1.1 [P] 在 `tests/test_settings_dictionary.py` 新增測試：驗證「Dictionary Set Creation Updates UI Immediately」——當 `_dict_engine` 提供時，呼叫 `_on_add_set` 後 `_current_set` 應更新且新辭典集應被選取
- [x] 1.2 [P] 在 `tests/test_settings_dictionary.py` 新增測試：驗證「Dictionary Set Creation Updates UI Immediately（engine unavailable）」——當 `_dict_engine is None` 時，`_on_add_set` 應觸發警告且不新增任何項目
- [x] 1.3 [P] 在 `tests/test_settings_dictionary.py` 新增測試：驗證「Checkbox Items Render Correctly」——所有 checkbox `QTableWidgetItem` 的 flags 包含 `ItemIsSelectable`

## 2. 修復 `_on_add_set`（Bug 1）

- [x] 2.1 修復 `_on_add_set`：分兩種情況處理（`airtype/ui/settings_dictionary.py`）——當 engine 為 None 時顯示 `QMessageBox.warning()` 並 return；當 engine 可用且建立成功後依序執行 `self._current_set = name`、`_reload_sets_list()`、`_load_set_data(name)`，實現「Dictionary Set Creation Updates UI Immediately」

## 3. 修復 Checkbox 渲染（Bug 2）

- [x] 3.1 [P] 修復 Checkbox 渲染：加入 `ItemIsSelectable` 至 `_set_hw_row`（`airtype/ui/settings_dictionary.py` col 0），修復「Checkbox Items Render Correctly on All Platforms」的 enabled checkbox
- [x] 3.2 [P] 修復 Checkbox 渲染：加入 `ItemIsSelectable` 至 `_set_rr_row`（`airtype/ui/settings_dictionary.py` col 0 enabled 與 col 3 regex），修復「Checkbox Items Render Correctly on All Platforms」的 regex checkbox

## 4. 驗證

- [x] 4.1 執行 `pytest tests/test_settings_dictionary.py -v` 確認所有測試通過
- [x] 4.2 手動執行 `python -m airtype` 開啟辭典設定頁，確認新增辭典集後清單正確更新，且 checkbox 顯示正確的打勾外觀
