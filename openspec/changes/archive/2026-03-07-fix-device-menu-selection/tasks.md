## 1. 使用 QActionGroup 實現互斥勾選

- [x] [P] 1.1 在 `_build_device_menu()` 中建立 `QActionGroup`（exclusive 模式），將所有裝置 action 設為 checkable，並根據 `config.voice.input_device` 設定初始勾選狀態（Audio Device Selector）
  - 測試：啟動應用程式，開啟膠囊裝置選單，確認當前設定的裝置旁顯示勾選標記

- [x] [P] 1.2 在 QMenu stylesheet 加入 indicator 樣式規則（`QMenu::indicator`），確保勾選符號在深色背景下清晰可見（checkmark visible on dark background）
  - 測試：開啟裝置選單，確認勾選符號在 `#1e293b` 背景上清晰可辨

## 2. 驗證

- [x] 2.1 手動測試完整流程：開啟選單確認初始勾選 → 切換裝置 → 重新開啟選單確認勾選跟隨（checkmark follows selection）
  - 測試：連續切換 2-3 次裝置，每次確認勾選標記正確移動
