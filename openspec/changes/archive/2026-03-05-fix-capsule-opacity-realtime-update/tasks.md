## 1. TDD — 撰寫失敗測試

- [x] 1.1 在 `tests/test_main.py` 新增測試，驗證 `main()` 初始化流程中 overlay appearance signals are connected at startup（opacity_changed / theme_changed / position_changed 均已連接至 overlay）

## 2. 實作修復

- [x] 2.1 在 `airtype/__main__.py` 的 UI 初始化區塊中，於 `SettingsWindow` 建立之後立即呼叫 `settings_window.connect_overlay(overlay)`（connect overlay after both objects are initialized）

## 3. 驗證

- [x] [P] 3.1 執行 `python -m pytest tests/test_main.py -v`，確認新增測試由 FAIL 轉為 PASS
- [x] [P] 3.2 執行 `python -m airtype`，開啟設定面板 → 外觀，拖動不透明度滑桿，確認膠囊視窗即時更新，不需重啟
