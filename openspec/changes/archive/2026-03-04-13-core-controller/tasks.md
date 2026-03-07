## 1. 狀態機

- [x] 1.1 建立 `airtype/core/controller.py`，透過 enum 與轉換表實作應用程式狀態機：6 個狀態（IDLE、ACTIVATING、LISTENING、PROCESSING、INJECTING、ERROR）— 驗證：應用程式狀態機需求、透過 enum 與轉換表實作狀態機需求
- [x] 1.2 實作基於 QObject 的控制器，搭配 state_changed、error、recognition_complete 等 Qt Signals — 驗證：基於 QObject 的控制器搭配 Qt Signals 需求

## 2. 事件處理

- [x] 2.1 連接快捷鍵事件至狀態轉換（切換啟動/停止、取消）
- [x] 2.2 連接管線事件（辨識完成、錯誤）至狀態轉換
- [x] 2.3 實作全域可存取的單例控制器，透過 `get_controller()` 存取 — 驗證：全域可存取的單例控制器需求

## 3. 生命週期

- [x] 3.1 實作啟動順序：建立控制器 → 載入設定 → 初始化元件 → 進入 IDLE
- [x] 3.2 實作關閉順序：卸載模型 → 停止音訊 → 清理

## 4. 相依套件

- [x] 4.1 將 `PySide6` 加入 `pyproject.toml` 核心相依套件

## 5. 測試

- [x] 5.1 撰寫狀態機轉換的單元測試（所有有效與無效轉換）
- [x] 5.2 撰寫取消行為的單元測試（任何活躍狀態按 Escape → IDLE）
