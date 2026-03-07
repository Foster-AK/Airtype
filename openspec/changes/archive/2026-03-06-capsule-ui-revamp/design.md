## Context

現有膠囊 overlay（`CapsuleOverlay`）佈局為水平排列：WaveformWidget (60x32 固定) → QLabel 狀態文字 (stretch=1) → DeviceSelector QComboBox (max 110px)，整體 300x60px。使用者反饋外觀不夠精簡，且缺乏直覺錄音控制。目標是重新設計為圖片所示的精煉佈局。

現有相關檔案：
- `airtype/ui/overlay.py` — CapsuleOverlay 主體
- `airtype/ui/waveform_widget.py` — 7 條音波動畫元件
- `airtype/ui/device_selector.py` — 裝置列舉函式 + QComboBox
- `airtype/core/controller.py` — CoreController 狀態機（私有 `_on_hotkey_start`/`_on_hotkey_stop`）

## Goals / Non-Goals

**Goals:**

- 音波圖置中展開，視覺上佔據膠囊主要區域
- 提供麥克風/停止切換按鈕，使用者可直接從膠囊控制錄音
- 裝置選擇以小型下拉箭頭呈現，節省空間
- 音波圖與控制按鈕之間有視覺分隔
- 狀態文字移至膠囊下方，膠囊主體更精簡
- 膠囊主體尺寸從 300x60 縮至約 220x48

**Non-Goals:**

- 不重新設計音波計算邏輯（`compute_bar_heights` 不變）
- 不修改動畫機制（滑入/滑出 + 淡入/淡出保留，僅調整數值）
- 不修改狀態色彩系統（`STATE_COLORS` 不變）
- 不重新設計設定面板中的外觀設定頁

## Decisions

### CapsuleBody 內部類別抽取

將圓角背景 `paintEvent` 從 `CapsuleOverlay` 抽取至新的 `CapsuleBody(QWidget)` 內部類別。`CapsuleOverlay` 改為外層容器（`QVBoxLayout`），包含 `CapsuleBody` + 底部 `status_label`。

**理由：** 狀態文字移至膠囊下方後，圓角背景不應覆蓋文字區域。分離繪製責任更清晰，`CapsuleBody` 只負責膠囊主體。

**替代方案：** 在 `paintEvent` 中限定繪製範圍至上半區域 — 但程式碼會更混亂且不易維護。

### 麥克風按鈕以 QPainter 自繪圖示

使用 `QPixmap` + `QPainter` 在程式碼中繪製麥克風和停止圖示，不依賴外部圖片資源。

**理由：** 與既有 `WaveformWidget` 的 QPainter 渲染風格一致，避免引入圖示檔案或圖示庫依賴。圖示簡單（麥克風輪廓 + 方形停止），QPainter 可輕鬆實現。

**替代方案：** 使用 Qt 內建 `QStyle.StandardPixmap` — 但內建圖示外觀因平台而異且不一定有合適的麥克風圖示。

### 裝置選擇改用 QToolButton + QMenu

將 `DeviceSelector QComboBox` 替換為 `QToolButton`（下拉箭頭）+ `QMenu`，複用既有 `list_input_devices()` 填充選單項目。

**理由：** QComboBox 在無邊框透明膠囊中難以精確控制外觀且佔用空間大。QToolButton + QMenu 可做成 20x32 的小型箭頭，視覺更精簡。`DeviceSelector` 類別保留供設定面板使用。

**替代方案：** 自訂 QComboBox 樣式 — 但無法有效縮至 20px 寬且 popup 行為難控制。

### WaveformWidget 彈性寬度

移除 `setFixedSize(60, 32)`，改為 `setMinimumWidth(80)` + `setFixedHeight(32)`，在 layout 中以 `stretch=1` 展開。

**理由：** 讓音波圖自動填滿膠囊中分隔線左側的所有空間，實現視覺置中。音波條間距計算（`paintEvent`）已基於 `self.width()` 動態分配，無需額外修改渲染邏輯。

### CoreController 新增公開方法

新增 `request_start()` 和 `request_stop()` 公開方法，內部分別委派至既有的 `_on_hotkey_start()` / `_on_hotkey_stop()`。

**理由：** UI 按鈕需要觸發錄音開始/停止，但 `_on_hotkey_*` 為私有方法（語意上僅供 HotkeyManager 呼叫）。新增公開方法提供明確的 UI 呼叫介面，不需變更狀態機邏輯。

### 拖曳行為移至 CapsuleBody

`mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` 移至 `CapsuleBody`。按鈕（QToolButton）會自動 `accept()` 點擊事件，不會傳播至 CapsuleBody 的拖曳處理。

**理由：** 維持既有拖曳功能，同時確保按鈕點擊不誤觸發拖曳。

## Risks / Trade-offs

- **[膠囊寬度變小]** 220px 可能在某些語系下讓底部狀態文字過長被截斷 → 狀態文字使用 `elide` 或自適應寬度
- **[QMenu 樣式]** 下拉選單預設外觀在透明視窗上可能突兀 → 自訂 QSS 使其風格與膠囊一致（深色背景 + 白色文字）
- **[位置計算]** 膠囊總高度因狀態文字顯示/隱藏而變化 → 使用 `setFixedWidth` + `setSizePolicy(Fixed, Minimum)` 讓高度自適應，`parse_pill_position` 預設值同步更新
- **[Linux WM 差異]** QToolButton + QMenu 在某些 tiling WM 上可能行為異常 → 現有 Qt.Tool 旗標已處理大部分情況，與既有 DeviceSelector QComboBox 風險相同
