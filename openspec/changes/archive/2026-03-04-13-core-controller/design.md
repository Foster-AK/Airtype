## 背景

核心控制器統籌所有元件，擁有應用程式狀態機，並將工作執行緒橋接至 Qt UI 執行緒。

相依性：04-hotkey-focus、12-recognition-pipeline。

## 目標 / 非目標

**目標：**

- 6 狀態機：IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → 回到 IDLE
- 處理快捷鍵、取消及錯誤轉換
- Qt Signal 橋接，實現執行緒安全的 UI 更新

**非目標：**

- 不含 UI 渲染（屬於 14-overlay-ui）
- 不直接處理音訊/ASR（委派給管線）

## 決策

### 基於 QObject 的控制器搭配 Qt Signals

CoreController 繼承 QObject 以使用 Qt Signals 進行執行緒安全通訊。工作執行緒發射 signals；UI 連接至 slots。這是標準的 PySide6 模式。

### 透過 enum 與轉換表實作狀態機

使用 Python Enum 定義狀態，以 dict 為基礎的轉換表定義有效轉換。無效轉換記錄日誌並忽略。狀態進入/離開的副作用透過 Qt Signals（state_changed / error / recognition_complete）及 callback 列表實現，取代原始構想的 per-transition hooks，以維持架構簡潔並避免過早抽象。

### 全域可存取的單例控制器

在應用程式啟動時建立單一 CoreController 實例，透過模組層級函式 `get_controller()` 存取。所有元件引用它進行狀態查詢和事件分發。

## 風險 / 取捨

- [風險] 高頻事件（例如 30fps 的 RMS）的 Qt Signal 開銷 → 緩解措施：批次 RMS 更新，最多每 33ms 發射一次
- [取捨] 單例模式降低可測試性 → 緩解措施：建構函式接受依賴注入以供測試
