## Why

辭典管理頁面（`SettingsDictionaryPage`）目前使用 `QSplitter` 分隔辭典集（左）與熱詞/替換規則（右），但同時以 `setFixedWidth(160)` 將左側固定，使拖動調整功能從未生效。這是多餘的複雜度，且造成 QSplitter 初始位置計算錯誤，導致兩側面板之間出現大段空白，需使用者手動點擊才能靠攏。

## What Changes

- 移除 `_build_ui()` 中的 `QSplitter`，改用 `QHBoxLayout` 直接排列左右兩側。
- 將左側辭典集面板（`_build_sets_panel()`）從 `QWidget` 改為 `QGroupBox`，與右側熱詞、替換規則的 `QGroupBox` 風格一致。
- 移除 `setFixedWidth(160)`，改用 `QHBoxLayout` 搭配 `setFixedWidth` 或 `addWidget(stretch=0/1)` 控制比例。
- 移除原先為修補 splitter bug 而規劃的 `showEvent()` 覆寫（不再需要）。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dictionary-ui`：辭典管理頁面左側辭典集區塊 SHALL 以 `QGroupBox` 呈現，整體佈局 SHALL 使用 `QHBoxLayout`，不使用可調整分割元件（`QSplitter`）。

## Impact

- Affected code: `airtype/ui/settings_dictionary.py`
