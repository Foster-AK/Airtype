## 1. 測試先行（TDD）

- [x] 1.1 [P] 撰寫測試：Settings Window Light Theme Background — 驗證 `_apply_content_bg("light")` 後 `_content_bg.styleSheet()` 含 `#ffffff`，`_nav_widget.styleSheet()` 含 `#fafafa`
- [x] 1.2 [P] 撰寫測試：Settings Window Dark Theme Background — 驗證 `_apply_content_bg("dark")` 後 `_content_bg.styleSheet()` 含 `#2d2d2d`，`_nav_widget.styleSheet()` 含 `#252525`
- [x] 1.3 [P] 撰寫測試：Settings Window Theme Change Response — 驗證 `_apply_content_bg("system")` 與 `"light"` 結果一致（`#ffffff`／`#fafafa`）
- [x] 1.4 [P] 撰寫測試：Navigation Panel Selection Style（pill）— 驗證 nav_list QSS 含 `margin`、`border-radius: 6px`、`#0a84ff`
- [x] 1.5 [P] 撰寫測試：Navigation Panel Hover State — 驗證 nav_list QSS 含 `hover` 及 `rgba(0, 0, 0, 0.06)`

## 2. 以 QSS objectName 選取器控制內容區背景

- [x] 2.1 在 `_build_ui()` 中建立 `self._content_bg = QWidget()`，設 `objectName("contentBg")`，以 `QVBoxLayout` 包裝 `QStackedWidget`，並以 `self._content_bg` 取代 `self.stacked` 加入根佈局
- [x] 2.2 在 `_build_nav()` 中將 `nav_widget` 存為 `self._nav_widget`，供後續主題更新使用

## 3. 新增 `_apply_content_bg(theme)` 實例方法

- [x] 3.1 在 `SettingsWindow` 中實作 `_apply_content_bg(theme: str) -> None`：`dark` 時設 content `#2d2d2d`、nav `#252525 border #444`；其餘設 content `#ffffff`、nav `#fafafa border #e0e0e0`
- [x] 3.2 在 `__init__` 結尾（`apply_theme()` 之後）呼叫 `self._apply_content_bg(config.appearance.theme)`
- [x] 3.3 在 `connect_overlay()` 中，於連接 `apply_theme` 後追加 `page.theme_changed.connect(self._apply_content_bg)`，實現 Settings Window Theme Change Response

## 4. 導覽列 QSS 改用內縮 pill 樣式

- [x] 4.1 更新 `_build_nav()` 中 `self.nav_list.setStyleSheet()`：`QListWidget::item` 加入 `margin: 2px 8px; border-radius: 6px;`；新增 `QListWidget::item:hover:!selected { background: rgba(0, 0, 0, 0.06); }`，完成 Navigation Panel Selection Style 與 Navigation Panel Hover State 兩項需求

## 5. 執行測試驗證

- [x] 5.1 執行 `pytest tests/test_settings_window.py -v`，確認所有測試通過（含新增的 1.1–1.5 測試）
