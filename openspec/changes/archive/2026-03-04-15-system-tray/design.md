## 背景

QSystemTrayIcon 提供跨平台系統匣支援。系統匣是疊層隱藏時的持續存取點。

相依性：13-core-controller。

## 目標 / 非目標

**目標：**

- 具狀態指示的系統匣圖示
- 含操作選項的右鍵選單
- 辨識完成時的通知
- 「關閉視窗 ≠ 結束」行為

**非目標：**

- 不嵌入設定面板（設定為獨立視窗）

## 決策

### QSystemTrayIcon 搭配動態圖示

使用 QSystemTrayIcon，針對 idle/listening/error 狀態搭配不同圖示。右鍵選單以 QMenu 建構。

### 透過 showMessage 發送通知

使用 `QSystemTrayIcon.showMessage()` 發送辨識通知。由 `general.notifications` 設定項控制。

### 關閉至系統匣行為

覆寫主視窗的 `closeEvent()` 以隱藏取代結束。只有系統匣選單的「結束」才真正退出應用程式。

## 風險 / 取捨

- [風險] Linux 需要 StatusNotifierItem（SNI）支援才能使用系統匣 → 緩解措施：檢查 SNI 可用性；若缺失則警告使用者
- [取捨] 通知樣式依作業系統而異 → 可接受；原生通知感覺更整合
