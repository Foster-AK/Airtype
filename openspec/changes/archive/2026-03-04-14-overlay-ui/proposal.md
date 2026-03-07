## 為什麼

浮動膠囊疊層是 Airtype 的主要 UI —— 一個不干擾使用者的膠囊，顯示錄音狀態、音波動畫及裝置選擇。它不得（SHALL NOT）從使用者的活躍應用程式搶走焦點。

參考：PRD §4.1（介面設計）、§4.1.1-4.1.3（膠囊規格）。

相依性：13-core-controller。

## 變更內容

- 實作浮動膠囊 QWidget（無邊框、透明、置頂、不搶焦點）
- 實作由 RMS 音訊資料驅動的 7 條動態音波元件
- 實作音訊裝置選擇下拉選單
- 實作滑入/滑出動畫與狀態驅動的樣式
- 連接至 CoreController 以進行狀態驅動的 UI 更新

## 功能

### 新增功能

- `overlay-ui`：浮動膠囊疊層，含音波動畫、裝置選擇器及狀態顯示

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/ui/overlay.py`、`airtype/ui/waveform_widget.py`、`airtype/ui/device_selector.py`、`tests/test_overlay.py`
- 相依套件：PySide6（已在 13 中加入）
- 相依於：13-core-controller
