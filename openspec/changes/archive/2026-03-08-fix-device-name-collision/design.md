## Context

Airtype 目前使用裝置名稱（字串）作為音訊裝置的識別方式，從 UI 選擇、config 儲存到 `sd.InputStream(device=...)` 的開啟全程使用名稱。在 Windows 系統上，同一隻實體麥克風會在多個 Host API（MME、DirectSound、WASAPI、WDM-KS）下以相同名稱出現，導致 sounddevice 的 `_get_device_id()` 發現多個匹配時拋出 `ValueError: Multiple input devices found`。

現有的 `list_input_devices()` 已按偏好 Host API 去重，但 UI 只儲存去重後的裝置名稱。當該名稱稍後傳給 sounddevice 時，sounddevice 再次查詢所有裝置（包含未去重的），因此仍會觸發衝突。

## Goals / Non-Goals

**Goals:**

- 消除多 Host API 同名裝置導致的 `ValueError`
- 保持「預設麥克風」選項正常運作
- 新舊設定檔向下相容（舊 config 中的 `"default"` 字串仍可正確讀取）

**Non-Goals:**

- 不處理裝置 index 在拔插/重啟後變動的全面映射（僅加 fallback 退回預設）
- 不改動裝置列舉邏輯本身（`list_input_devices` 的去重與 Host API 偏好邏輯不變）
- 不實作裝置名稱 → index 的持久化映射表

## Decisions

### 以裝置 index 取代裝置名稱作為識別值

`list_input_devices()` 已回傳 `{"index": int, "name": str}`，UI 目前只用 `name` 作為 itemData。改為用 `index` 作為 itemData，config 存 int，傳給 sounddevice 時直接用 int index。

**替代方案**：用 `"{name}, {hostapi_name}"` 格式作為唯一識別 — 但 sounddevice 仍會做子字串匹配，無法保證唯一，且依賴 Host API 名稱字串的穩定性。

### Config 欄位型別擴展為 Union

`VoiceConfig.input_device` 從 `str` 改為 `str | int`，保留 `"default"` 字串作為系統預設的特殊值。JSON 序列化天然支援 int，`from_dict` 的 `_fill()` 直接取值不需額外轉換。

### Signal 型別改為 object

`DeviceSelector.device_changed` 和 `VoiceSettingsPage.device_changed` 的 Signal 型別從 `Signal(str)` 改為 `Signal(object)`，以同時支援 int 和 `"default"` 字串。

### 新增裝置 index 無效時的 fallback

在 `AudioCaptureService.start()` 中，若以 int index 開啟串流失敗（裝置不存在），自動退回 `device=None`（系統預設）並記錄警告。這處理了裝置 index 在重啟後改變的邊界情況。

## Risks / Trade-offs

- **[裝置 index 不穩定]** → 拔插裝置或重啟後 index 可能改變，導致設定中儲存的 index 指向錯誤裝置。Mitigation：fallback 至系統預設裝置，使用者手動重新選擇即可。
- **[舊 config 相容]** → 舊版 config 中 `input_device` 可能是非 `"default"` 的裝置名稱字串。Mitigation：`audio_capture.py` 中 `sd.InputStream(device=str)` 仍可接受字串，若仍觸發多裝置衝突則被 fallback 捕獲退回預設。
