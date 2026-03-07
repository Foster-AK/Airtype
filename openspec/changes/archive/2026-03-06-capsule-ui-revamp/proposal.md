## Why

現有膠囊 overlay 佈局（音波圖靠左 → 狀態文字 → 裝置選擇器）視覺不夠精簡，且缺乏直覺的錄音控制按鈕。使用者需要透過快捷鍵才能開始/停止錄音，膠囊本身無法直接操作。本次調整將膠囊重新設計為更精煉的佈局：音波圖置中、新增麥克風/停止切換按鈕、裝置下拉選單以小型箭頭按鈕呈現，並將狀態文字移至膠囊下方。

## What Changes

- 音波圖（WaveformWidget）從固定 60x32 改為彈性寬度（stretch=1），置中填滿可用空間
- 新增麥克風/停止切換按鈕（QToolButton），按下開始錄音顯示停止圖示，按停止變回麥克風圖示
- 裝置選擇器從 QComboBox 改為 QToolButton + QMenu 下拉箭頭按鈕，更精簡
- 音波圖與麥克風按鈕之間新增垂直分隔線（QFrame VLine）
- 狀態文字從膠囊內部移至膠囊下方獨立 QLabel，IDLE 時隱藏
- 膠囊主體抽取為 CapsuleBody 內部類別，獨立負責圓角背景繪製
- 膠囊尺寸從 300x60 縮小為約 220x48（主體高度）
- CoreController 新增 `request_start()` / `request_stop()` 公開方法供 UI 按鈕呼叫

## Capabilities

### New Capabilities

（無新增 capability）

### Modified Capabilities

- `overlay-ui`: 膠囊佈局重構——音波圖置中、新增麥克風按鈕與裝置下拉選單、分隔線、狀態文字移至下方
- `core-controller`: 新增 `request_start()` / `request_stop()` 公開方法，供 UI 按鈕觸發錄音開始/停止

## Impact

- 受影響程式碼：
  - `airtype/ui/overlay.py` — 主要重構：layout、CapsuleBody、麥克風按鈕、裝置下拉選單
  - `airtype/ui/waveform_widget.py` — 移除固定尺寸，改彈性寬度
  - `airtype/core/controller.py` — 新增公開方法
  - `tests/test_overlay.py` — 更新既有測試 + 新增按鈕/選單/分隔線測試
- 受影響 spec：`overlay-ui`、`core-controller`
- 不影響 `device_selector.py`（保留 `list_input_devices()` 供複用）
- 不影響音波計算邏輯、動畫機制、狀態色彩
