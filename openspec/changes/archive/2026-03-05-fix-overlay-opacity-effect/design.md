## Context

CapsuleOverlay 使用 `QGraphicsOpacityEffect` 實作淡入/淡出動畫。目前此 effect 在 `__init__` 中建立並永久掛載於 widget 上，即使動畫結束（opacity=1.0）仍持續存在。

`QGraphicsOpacityEffect` 的運作機制是將整個 widget 及其子元件渲染到離屏緩衝區（offscreen pixmap），再以指定的 opacity 繪製到螢幕。在 Windows 上，當 QComboBox（DeviceSelector）的 dropdown popup 開啟/關閉時，此離屏緩衝區未正確失效或重繪，導致 `paintEvent` 繪製的圓角膠囊背景出現異常。

目前的程式碼結構（`airtype/ui/overlay.py`）：
- `__init__`：建立 `QGraphicsOpacityEffect` 並永久掛載（第 150-153 行）
- `_setup_animations`：預建立 4 個 `QPropertyAnimation`（slide_in、slide_out、fade_in、fade_out）（第 190-212 行）
- `show_animated`：同時啟動 slide_in + fade_in（第 250-261 行）
- `hide_animated`：同時啟動 slide_out + fade_out（第 263-274 行）
- `_on_slide_out_done`：隱藏視窗，重設 opacity 為 1.0（第 276-279 行）

## Goals / Non-Goals

**Goals：**

- 修復切換 DeviceSelector 後膠囊背景變色/消失的 bug
- 保留滑入淡入（200ms）、滑出淡出（150ms）的動畫效果
- 正常可見狀態下移除離屏渲染路徑

**Non-Goals：**

- 不變更動畫時間、緩動曲線等視覺參數
- 不變更 DeviceSelector 或 WaveformWidget 的行為
- 不修改全域樣式表或主題系統

## Decisions

### 臨時掛載 QGraphicsOpacityEffect

**選擇**：在 `show_animated` / `hide_animated` 中即時建立 `QGraphicsOpacityEffect`，動畫結束後呼叫 `setGraphicsEffect(None)` 移除。

**替代方案**：
- **使用 `setWindowOpacity()`**：Qt 的 `windowOpacity` 屬性可直接動畫化，但此屬性影響整個 native window 的合成透明度，與 `WA_TranslucentBackground` 的自訂 `paintEvent` 渲染互動行為在各平台不一致。
- **在 `paintEvent` 中手動實作透明度**：可行但需大幅重構，且無法自動對子元件（QLabel、QComboBox）套用透明度。

**理由**：臨時掛載方案改動最小，完全保留現有動畫效果，且僅影響動畫進行中的短暫時間（200ms/150ms），正常操作時不經過離屏渲染。

### 動畫衝突防護

**選擇**：在 `show_animated` / `hide_animated` 開頭，先停止可能正在進行的動畫並清除舊 effect。

**理由**：若使用者快速連續觸發 show/hide（例如快速切換語音輸入），新的 `setGraphicsEffect()` 會取代舊的，可能導致舊動畫的 `finished` signal 行為未定義。先 stop 再建立可避免此問題。

## Risks / Trade-offs

- **[每次動畫建立新物件]** → 每次 show/hide 動畫建立新的 `QGraphicsOpacityEffect` 和 `QPropertyAnimation`。影響極小：這些物件很輕量，且動畫結束後即被垃圾回收。
- **[setGraphicsEffect(None) 行為]** → `setGraphicsEffect(None)` 會刪除（delete）當前 effect 物件。正在進行的動畫引用已刪除的 effect 會導致問題，因此必須先 stop 動畫再移除 effect。已透過「動畫衝突防護」決策緩解。
- **[平台差異]** → 此 bug 主要在 Windows 上重現。修復後在 macOS/Linux 上的行為不應有變化（正常渲染路徑在所有平台都正確）。
