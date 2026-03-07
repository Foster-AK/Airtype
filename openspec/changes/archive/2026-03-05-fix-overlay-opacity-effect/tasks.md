## 1. 移除永久 QGraphicsOpacityEffect（臨時掛載 QGraphicsOpacityEffect）

- [x] 1.1 移除 `CapsuleOverlay.__init__` 中永久建立並掛載 `QGraphicsOpacityEffect` 的程式碼（第 150-153 行），以及 `_setup_animations` 中預建立 `_fade_in` / `_fade_out` 動畫的程式碼（第 202-212 行）

## 2. 實作臨時 Slide Animation 淡入/淡出（臨時掛載 QGraphicsOpacityEffect）

- [x] 2.1 修改 `show_animated` 的 Slide Animation 淡入：建立臨時 `QGraphicsOpacityEffect`（opacity=0.0），掛載至 widget，建立 `QPropertyAnimation` 執行淡入（0→1），連接 `finished` signal 至 `_on_fade_in_done`
- [x] [P] 2.2 修改 `hide_animated`：建立臨時 `QGraphicsOpacityEffect`（opacity=1.0），掛載至 widget，建立 `QPropertyAnimation` 執行淡出（1→0）
- [x] 2.3 新增 `_on_fade_in_done` slot：呼叫 `setGraphicsEffect(None)` 移除 effect，確保正常可見狀態無 QGraphicsEffect
- [x] 2.4 修改 `_on_slide_out_done`：以 `setGraphicsEffect(None)` 取代原本的 `self._opacity_effect.setOpacity(1.0)`

## 3. 動畫衝突防護

- [x] 3.1 在 `show_animated` / `hide_animated` 開頭加入防護邏輯：停止可能正在進行的 fade 動畫，清除舊 effect，避免快速連續呼叫時的衝突

## 4. 驗證：膠囊背景於裝置切換後保持正常

- [x] 4.1 執行既有測試 `python -m pytest tests/test_overlay.py -v`，確認全數通過
- [x] [P] 4.2 手動測試：啟動應用 → 在膠囊上反覆切換 DeviceSelector → 確認圓角背景保持正常（Capsule Background Preserved After Device Switch）
- [x] [P] 4.3 手動測試：確認 show_animated / hide_animated 的滑入淡入、滑出淡出動畫效果正常（No Graphics Effect After Show Animation）
