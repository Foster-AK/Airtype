## Context

膠囊 overlay 的音效裝置選單（`QToolButton` + `QMenu`）目前未標記已選取的裝置。現有 spec 已要求 "indicate the currently selected device"，但 `_build_device_menu()` 實作中遺漏了勾選標記邏輯。設定視窗（`settings_voice.py`）使用 `QComboBox`，天然顯示選取項，不受影響。

## Goals / Non-Goals

**Goals:**

- 在膠囊裝置選單中以勾選標記顯示當前選取的裝置
- 切換裝置後勾選標記自動跟隨
- 深色背景下勾選符號清晰可見

**Non-Goals:**

- 不修改設定視窗的裝置選擇元件
- 不改變裝置選擇的儲存邏輯或音訊切換流程
- 不新增裝置熱插拔偵測

## Decisions

### 使用 QActionGroup 實現互斥勾選

使用 Qt 內建的 `QActionGroup`（exclusive 模式）管理所有裝置 action，而非手動追蹤勾選狀態。

**理由**：`QActionGroup` 是 Qt 標準的 radio-button-in-menu 做法，自動處理互斥切換，無需在 `_on_device_selected()` 中手動遍歷清除舊勾選。

**替代方案**：手動在 `_on_device_selected()` 中迭代所有 action 並切換 checked 狀態。雖然可行，但增加樣板程式碼且容易出錯。

### 在 QMenu stylesheet 加入 indicator 樣式

在現有深色主題 stylesheet 中加入 `QMenu::indicator` 規則，使用白色邊框與白色勾選符號，確保在 `#1e293b` 背景上清晰可見。

**理由**：Qt 預設的 indicator 在深色背景下可能不可見或使用系統主題色，需明確設定顏色。

## Risks / Trade-offs

- **[風險]** 部分平台的 QMenu indicator 渲染差異 → 使用純 stylesheet 定義外觀，不依賴平台原生繪製
- **[限制]** 選單在每次建構時靜態填充裝置清單 → 此為既有行為，不在本次修改範圍
