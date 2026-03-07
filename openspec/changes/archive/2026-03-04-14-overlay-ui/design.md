## 背景

浮動膠囊是 Airtype 的標誌性 UI 元素。PRD §4.1 定義了尺寸、顏色、動畫和佈局的詳細規格。

相依性：13-core-controller。

## 目標 / 非目標

**目標：**

- 無邊框、透明、置頂的 QWidget，不搶走焦點
- 由音訊 RMS 驅動的 7 條音波動畫
- 音訊裝置下拉選擇器
- 滑入/滑出動畫（200ms 出現、150ms 消失）
- 狀態驅動的顏色與文字變更

**非目標：**

- 不含設定面板（屬於 16）
- 不含系統匣（屬於 15）

## 決策

### 使用 Qt Tool 視窗旗標實現不搶焦點

使用 `Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint` 搭配 `setAttribute(Qt.WA_ShowWithoutActivating)`。這可防止膠囊從使用者的活躍視窗搶走焦點。

### 基於 QPainter 的自訂音波渲染

在 `paintEvent()` 中使用 QPainter 繪製音波條。避免依賴 QML/QtQuick 並可完全控制動畫。以計時器驅動重繪，達到 30+ FPS。

### 膠囊位置持久化

將上次位置儲存於設定檔（`appearance.pill_position`）。支援「置中」、「游標附近」及自訂 x,y 座標。可拖曳並記憶位置。

## 風險 / 取捨

- [風險] Qt.Tool 旗標在不同 Linux 視窗管理器上行為不一 → 緩解措施：在 GNOME、KDE、i3 上測試；提供備援旗標
- [取捨] QPainter 渲染受限於 CPU → 對 7 條音波條而言可接受；若效能分析顯示問題再最佳化
