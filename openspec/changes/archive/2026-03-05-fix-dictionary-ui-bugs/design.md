## Context

`SettingsDictionaryPage`（`airtype/ui/settings_dictionary.py`）是辭典設定的核心 UI 元件，提供：
- 左側辭典集清單（`QListWidget`，支援勾選啟用）
- 右上熱詞表格（`QTableWidget`，含啟用 checkbox）
- 右下替換規則表格（`QTableWidget`，含啟用 / regex checkbox）

目前程式碼中存在兩個可重現的問題：辭典集新增後 UI 不更新、以及 Windows 上 `QTableWidgetItem` checkbox 渲染異常。

## Goals / Non-Goals

**Goals:**

- 修復 `_on_add_set`：正確處理 engine 有無的兩種情況，確保新增後 UI 即時反映並切換至新辭典集
- 修復 `_set_hw_row` / `_set_rr_row`：為所有 checkbox `QTableWidgetItem` 補上 `ItemIsSelectable` flag，解決 Windows 渲染異常
- 不引入任何新的 public API 或 widget

**Non-Goals:**

- 重構 `SettingsDictionaryPage` 的整體架構
- 修改 `DictionaryEngine` 本身
- 支援 `_dict_engine is None` 下的完整辭典集管理（此為降級模式，只給警告提示）

## Decisions

### 修復 `_on_add_set`：分兩種情況處理

**情況 A（`_dict_engine is None`）：**

現行程式碼在 engine 為 None 時靜默略過，無任何回饋。

決策：改為顯示 `QMessageBox.warning()`，明確告知使用者「辭典引擎尚未初始化，無法新增辭典集」，並提前 return。這比無聲失敗更符合 UX 原則，也讓問題可追蹤。

**情況 B（`_dict_engine is not None`）：**

現行程式碼在 `create_set()` / `save_set()` 成功後，未更新 `self._current_set` 也未呼叫 `_load_set_data()`。

決策：成功建立後，依序執行：
1. `self._current_set = name`（更新邏輯狀態，讓 `_reload_sets_list` 自動選取新辭典集）
2. `self._reload_sets_list()`（重整清單）
3. `self._load_set_data(name)`（載入新辭典集的空內容至表格）

這三步驟順序不可調換，因為 `_reload_sets_list()` 依賴 `self._current_set` 決定選取哪一行。

### 修復 Checkbox 渲染：加入 `ItemIsSelectable`

Windows PySide6 style engine（`QWindowsVistaStyle` / `QFusionStyle`）在繪製 checkbox indicator 時，需要 item 具有 `ItemIsSelectable` flag 才能正確渲染帶 checkmark 的方框。缺少此 flag 時，style engine 退回 filled 黑色矩形。

決策：在 `_set_hw_row` 及 `_set_rr_row` 中，所有純 checkbox 用途的 `QTableWidgetItem` 均加入 `Qt.ItemFlag.ItemIsSelectable`：

```python
# 修改前
chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)

# 修改後
chk.setFlags(
    Qt.ItemFlag.ItemIsUserCheckable
    | Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsSelectable
)
```

影響位置（共 3 處）：
| 方法 | 欄位 | 說明 |
|------|------|------|
| `_set_hw_row` | col 0 | 熱詞啟用 checkbox |
| `_set_rr_row` | col 0 | 替換規則啟用 checkbox |
| `_set_rr_row` | col 3 | 替換規則 regex checkbox |

`ItemIsSelectable` 不影響點擊行為（checkbox 切換仍由 `ItemIsUserCheckable` 控制），只影響視覺渲染。在 macOS / Linux 上此 flag 本就存在或不影響渲染，因此跨平台安全。

## Risks / Trade-offs

- [Risk] 加入 `ItemIsSelectable` 後，使用者可以「選取」純 checkbox 的格子，導致整行 row 被選取時 checkbox 格子也被反白 → Mitigation：表格已設定 `SelectRows` 模式，整行選取是預期行為，不影響功能。
- [Risk] `_reload_sets_list()` 的 `blockSignals` 範圍需要確認不會遮蔽 `_load_set_data` 後的 `currentRowChanged` 信號 → Mitigation：`_load_set_data` 在 `blockSignals(False)` 之後才被呼叫，信號不受影響。
