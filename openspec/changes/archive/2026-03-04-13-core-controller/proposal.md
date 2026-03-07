## 為什麼

核心控制器是中央協調器，負責管理應用程式狀態轉換、在模組之間分發事件，並透過 Qt Signals 將工作執行緒橋接至 Qt UI 執行緒。它實作主要狀態機（IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE）。

參考：PRD §8.1（應用程式狀態機）、§3.2（核心控制器）。

相依性：04-hotkey-focus、12-recognition-pipeline。

## 變更內容

- 實作 `CoreController` 及 6 狀態應用程式狀態機
- 處理快捷鍵事件 → 觸發管線啟動/停止/取消
- 透過 QObject signals 將工作執行緒事件橋接至 Qt 主執行緒
- 管理生命週期：啟動 → 閒置 → 活躍 → 關閉

## 功能

### 新增功能

- `core-controller`：中央應用程式狀態機、事件分發及 Qt Signal 整合

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/controller.py`、`tests/test_controller.py`
- 新增相依套件：PySide6（用於 QObject/Signal，首次使用 PySide6）
- 相依於：04-hotkey-focus、12-recognition-pipeline
