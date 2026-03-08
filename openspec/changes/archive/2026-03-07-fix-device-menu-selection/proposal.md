## Problem

膠囊（overlay）主畫面的音效輸入裝置下拉選單使用 `QToolButton` + `QMenu` 實作，但建立選單時未標記當前已選取的裝置。使用者打開選單後無法辨識哪個裝置是目前正在使用的，需要到設定視窗才能確認。

## Root Cause

`_build_device_menu()` 僅建立 `QAction` 並連接 `triggered` 信號，但未將 action 設為 `checkable`，也未根據 `self._config.voice.input_device` 設定勾選狀態。選單中所有項目看起來完全相同，缺乏視覺區分。

## Proposed Solution

1. 在 `_build_device_menu()` 中使用 `QActionGroup`（exclusive 模式）管理所有裝置 action
2. 將每個 action 設為 `setCheckable(True)`
3. 根據 `self._config.voice.input_device` 對匹配的 action 設定 `setChecked(True)`
4. 在 QMenu stylesheet 加入 `QMenu::indicator` 樣式，確保勾選符號在深色背景下清晰可見
5. `_on_device_selected()` 中 `QActionGroup` 的 exclusive 屬性自動處理勾選狀態切換

## Success Criteria

- 開啟膠囊裝置選單時，當前設定的裝置旁顯示勾選標記
- 切換裝置後重新打開選單，勾選標記正確跟隨至新選取的裝置
- 深色背景下勾選符號清晰可見

## Capabilities

### New Capabilities

（無）

### Modified Capabilities

- `overlay-ui`: 裝置選單新增勾選標記以顯示當前選取的裝置

## Impact

- 修改檔案：`airtype/ui/overlay.py`
- 影響範圍：僅膠囊 UI 的裝置選單視覺回饋，不影響音訊功能或設定儲存邏輯
