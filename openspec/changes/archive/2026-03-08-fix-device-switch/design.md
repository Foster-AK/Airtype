## Context

目前 `CapsuleOverlay` 和 `SettingsVoicePage` 兩個 UI 元件在使用者切換音訊裝置時，都只更新 `config.voice.input_device`，不通知 `AudioCaptureService` 重啟串流。`__main__.py` 中原本設計了 Signal 連接（第 282-284 行），但因為 `overlay` 上不存在 `_device_selector` 屬性（`DeviceSelector` 被 import 但從未實例化），`hasattr` 永遠回傳 `False`，連接從未建立。

`AudioCaptureService.set_device()` 已正確實作：停止舊串流 → 更新 config → 以新裝置重啟串流。問題純粹在於 Signal 未連接。

## Goals / Non-Goals

**Goals:**

- 使用者從膠囊 UI 或設定視窗切換裝置後，音訊擷取立即切換到新裝置
- 維持現有解耦架構（UI 不直接持有 AudioCaptureService 參考）

**Non-Goals:**

- 不重構 overlay 的裝置選單為 DeviceSelector 元件（現有 QMenu 方案可用）
- 不修改 AudioCaptureService 的 set_device() 實作
- 不新增設定變更觀察者模式（本次只修復 Signal 斷線）

## Decisions

### 在 CapsuleOverlay 新增 device_changed Signal

在 `CapsuleOverlay` class 層級新增 `device_changed = Signal(str)`，在 `_on_device_selected()` 中 emit。這比改用 `DeviceSelector` 元件簡單——overlay 已有完整的 QMenu + QActionGroup 實作，只缺 Signal 通知。

替代方案：將 QMenu 替換為 DeviceSelector 元件 → 改動過大，且 QMenu 的視覺效果（checkmark、exclusive）已完善。

### 在 SettingsVoicePage 新增 device_changed Signal

在 `SettingsVoicePage` class 層級新增 `device_changed = Signal(str)`，在 `_on_device_changed()` 中 emit。`Signal` 已在該檔案 import。

### 修正 __main__.py Signal 連接

移除失效的 `hasattr(overlay, "_device_selector")` 條件，直接連接 `overlay.device_changed` 和 `settings_window._page_voice.device_changed` 到 `audio_capture.set_device()`。

替代方案：加入 config 變更觀察者模式 → 過度設計，本次只有裝置切換一個場景需要即時通知。

## Risks / Trade-offs

- **冗餘 config 更新**：overlay/settings 先設定 `config.voice.input_device`，`set_device()` 內部又設定一次 → 無害（值相同），不值得為此重構。
- **兩個 UI 可能同時觸發**：使用者不太可能同時操作兩個 UI，且都在 GUI thread 中執行，無競爭條件。
