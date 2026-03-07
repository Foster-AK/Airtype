## Problem

在浮動膠囊 overlay 上透過 DeviceSelector（QComboBox）下拉選單切換音訊輸入裝置後，膠囊的圓角背景會變色或消失。需重啟程式或在設定視窗重新調整外觀設定才能恢復正常顯示。

## Root Cause

`CapsuleOverlay` 在 `__init__` 中永久掛載 `QGraphicsOpacityEffect`，即使 opacity 設為 1.0，此 effect 仍強制所有渲染經由離屏緩衝區（offscreen pixmap）。在 Windows 上，當 QComboBox（DeviceSelector）的 dropdown popup 開啟/關閉時，離屏緩衝區未正確重繪，導致 `paintEvent` 繪製的圓角膠囊背景出現異常（變色或消失）。

根本原因在 `airtype/ui/overlay.py` 第 150-153 行：

```python
self._opacity_effect = QGraphicsOpacityEffect(self)
self._opacity_effect.setOpacity(1.0)
self.setGraphicsEffect(self._opacity_effect)
```

此 effect 僅在 show/hide 的淡入淡出動畫（200ms/150ms）期間有用，但在正常可見狀態下仍持續掛載，造成不必要的離屏渲染路徑。

## Proposed Solution

將 `QGraphicsOpacityEffect` 從永久掛載改為僅在動畫期間臨時使用：

- **顯示時（show_animated）**：建立臨時 `QGraphicsOpacityEffect`，執行淡入動畫（0→1），動畫結束後移除 effect
- **隱藏時（hide_animated）**：建立臨時 `QGraphicsOpacityEffect`，執行淡出動畫（1→0），隱藏完成後移除 effect
- **正常可見狀態**：無 graphics effect，widget 直接渲染，避免離屏緩衝區問題

## Success Criteria

- 在膠囊 overlay 上反覆切換 DeviceSelector 裝置後，圓角膠囊背景保持正常顯示
- show_animated / hide_animated 的滑入淡入、滑出淡出動畫效果與修改前一致
- 既有 `tests/test_overlay.py` 全數通過

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `overlay-ui`：動畫實作從永久 QGraphicsOpacityEffect 改為臨時掛載/卸除，屬於實作細節變更，不影響 spec 層級的需求定義

## Impact

- 受影響程式碼：`airtype/ui/overlay.py`（唯一需修改的檔案）
- 受影響功能：CapsuleOverlay 的 show/hide 動畫機制
- 不影響：設定視窗、DeviceSelector、WaveformWidget、其他 UI 元件
