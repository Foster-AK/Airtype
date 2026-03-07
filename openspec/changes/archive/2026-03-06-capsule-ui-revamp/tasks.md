## 1. WaveformWidget 彈性寬度

- [x] [P] 1.1 修改 `airtype/ui/waveform_widget.py`：移除 `setFixedSize(60, 32)`，改為 `setMinimumWidth(80)` + `setFixedHeight(32)`，實現 Waveform Animation 彈性寬度。驗證：widget 的 `minimumWidth()` 為 80、`sizePolicy` 允許水平擴展

## 2. CoreController 公開方法

- [x] [P] 2.1 在 `airtype/core/controller.py` 實作 CoreController 新增公開方法（Public Recording Control Methods）：`request_start()` 委派至 `_on_hotkey_start()`、`request_stop()` 委派至 `_on_hotkey_stop()`。驗證：IDLE 時呼叫 `request_start()` 可轉入 LISTENING；LISTENING 時呼叫 `request_stop()` 可轉入 PROCESSING

## 3. CapsuleBody 內部類別抽取

- [x] 3.1 在 `airtype/ui/overlay.py` 新增 `CapsuleBody(QWidget)` 內部類別，實現 CapsuleBody Separation：將圓角背景 `paintEvent` 從 `CapsuleOverlay` 移入 `CapsuleBody`，設定 `setFixedHeight(48)`。驗證：`CapsuleBody` 可獨立繪製圓角背景

## 4. 膠囊主體佈局重構

- [x] 4.1 重寫 `CapsuleOverlay._setup_ui()`：外層 `QVBoxLayout` 包含 `CapsuleBody` + `status_label`，`CAPSULE_WIDTH` 改為 220。`CapsuleBody` 內 `QHBoxLayout` 放置 WaveformWidget(stretch=1)。拖曳行為移至 CapsuleBody。驗證：膠囊寬度 220px、音波圖可擴展填滿空間

- [x] 4.2 新增 Vertical Separator：在 CapsuleBody layout 中音波圖右側加入 QFrame VLine（1x24px, rgba 255,255,255,0.3）。驗證：分隔線存在且可見

- [x] 4.3 新增 Microphone Toggle Button（麥克風按鈕以 QPainter 自繪圖示）：QToolButton 32x32，QPainter 繪製麥克風/停止圖示，點擊呼叫 `controller.request_start()` 或 `request_stop()`。驗證：IDLE 顯示麥克風圖示、LISTENING 顯示停止圖示、點擊觸發對應 controller 方法

- [x] 4.4 新增 Device Dropdown Button（裝置選擇改用 QToolButton + QMenu）：QToolButton 20x32 下拉箭頭 + QMenu，複用 `list_input_devices()` 填充 Audio Device Selector 選單，首項為「預設麥克風」。驗證：選單包含預設選項、選擇裝置更新 config

## 5. 狀態驅動 UI 更新

- [x] 5.1 更新 `set_state()` 方法：切換 mic_button 圖示（IDLE=麥克風、其他=停止）、控制 Status Label Below Capsule 可見性（IDLE 隱藏、其他顯示）、保留背景色與音波顏色邏輯。驗證：各狀態下圖示與文字正確

- [x] 5.2 更新 `parse_pill_position` 預設常數與 Capsule Position Persistence 中拖曳行為，確保 Button Click Does Not Trigger Drag。驗證：拖曳 CapsuleBody 可重新定位、按鈕點擊不觸發拖曳

- [x] 5.3 調整滑入/滑出動畫的偏移量與位置計算以適配新尺寸。驗證：動畫視覺正確

## 6. 測試更新

- [x] [P] 6.1 更新 `tests/test_overlay.py` 既有測試：修正尺寸常數斷言、調整 layout 相關測試

- [x] [P] 6.2 新增 Microphone Toggle Button 測試：圖示切換、click 呼叫 controller `request_start` / `request_stop`

- [x] [P] 6.3 新增 Device Dropdown Button 測試：選單有預設選項、選擇裝置更新 config

- [x] [P] 6.4 新增 Vertical Separator 存在性測試、Status Label Below Capsule 可見性測試（IDLE 隱藏/LISTENING 顯示）、CapsuleBody Separation 背景繪製測試
