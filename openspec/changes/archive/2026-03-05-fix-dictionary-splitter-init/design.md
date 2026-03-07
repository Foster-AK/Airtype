## Context

`SettingsDictionaryPage._build_ui()` 原本使用 `QSplitter(Horizontal)` 分隔辭典集（左）與熱詞/替換規則（右）。然而左側同時設有 `setFixedWidth(160)`，使 QSplitter 的拖動調整功能從未生效，且引發初始位置計算錯誤（兩側之間出現空白）。右側熱詞與替換規則已各自以 `QGroupBox` 呈現，左側辭典集卻使用 plain `QWidget` 加 bold `QLabel` 標題，風格不一致。

## Goals / Non-Goals

**Goals:**

- 以 `QHBoxLayout` 取代 `QSplitter`，消除多餘的分割元件。
- 左側辭典集改用 `QGroupBox`，與右側兩個 QGroupBox 風格一致。
- 進入頁面時兩側面板自然靠攏，無多餘空白，不需任何修補邏輯。

**Non-Goals:**

- 不改變辭典集面板的寬度比例設計（維持左側約 160px）。
- 不重構資料層或事件處理邏輯。
- 不新增使用者可調整寬度的功能（現階段不需要）。

## Decisions

### 以 QHBoxLayout 取代 QSplitter

`_build_ui()` 中建立 `QHBoxLayout`，以 `addWidget(left, stretch=0)` 加入左側固定寬度面板，以 `addWidget(right, stretch=1)` 加入右側填滿面板。這比 QSplitter 更直接，不會有初始位置 bug，也不需要 `showEvent` 修補邏輯。

### 左側辭典集改為 QGroupBox

`_build_sets_panel()` 回傳 `QGroupBox`（標題使用 `tr("settings.dictionary.sets_label")`），移除原本的 bold `QLabel` 標題（由 QGroupBox title 取代）。`setFixedWidth(160)` 移至 QGroupBox 上。與右側 `_build_hot_words_group()` 及 `_build_replace_rules_group()` 的 QGroupBox 風格統一。

## Risks / Trade-offs

- **[取捨] 移除 QSplitter 後使用者無法調整左右比例** → 現階段辭典集名稱長度有限，160px 足夠；若未來有需求可再引入可調整佈局。
- **[取捨] QGroupBox 標題與原 bold QLabel 外觀略有差異** → 視覺一致性提升（三個 GroupBox 統一），可接受。
