## 1. 核心實作：Audio Stream Capture WASAPI auto_convert 平台特定設定

- [x] [P] 1.1 在 `airtype/core/audio_capture.py` 新增 `_build_extra_settings()` 靜態方法（抽取 `_build_extra_settings()` 輔助方法），回傳 `sd.WasapiSettings(auto_convert=True)`（Windows）或 `None`（其他平台）。測試標準：方法存在且可呼叫，Windows 上回傳 WasapiSettings 實例，非 Windows 回傳 None。
- [x] 1.2 修改 Audio Stream Capture 主路徑（`AudioCaptureService.start()`），將 `_build_extra_settings()` 結果傳入 `sd.InputStream(extra_settings=...)`，確保 WASAPI auto_convert on Windows 與 Non-Windows platform 情境正確。測試標準：mock InputStream 驗證 extra_settings 參數正確傳遞。
- [x] 1.3 修改 Audio Stream Capture fallback 路徑（裝置 index 無效時退回預設裝置），同樣傳入 `extra_settings`，確保 Fallback path uses WASAPI auto_convert 情境正確。測試標準：mock 主路徑失敗後，fallback InputStream 也收到 extra_settings。
- [x] 1.4 確認 WASAPI auto_convert fallback on non-WASAPI Host API 情境：當 `sd.WasapiSettings` 建構拋出例外時，`_build_extra_settings()` 回傳 `None`，串流正常開啟。測試標準：mock WasapiSettings 拋出 AttributeError，驗證 extra_settings 為 None 且串流成功。

## 2. 設定頁面：Voice Settings Page 麥克風測試同步修復

- [x] [P] 2.1 修改 Voice Settings Page 的 `_MicTestWorker.run()`（`airtype/ui/settings_voice.py`），在 `sd.InputStream` 加入 `extra_settings`（Microphone test uses WASAPI auto_convert on Windows），確保麥克風測試功能對不支援 16kHz 的裝置也能正常運作。測試標準：手動或 mock 測試驗證 InputStream 收到 extra_settings。

## 3. 測試

- [x] [P] 3.1 在 `tests/test_audio_capture.py` 新增測試案例：驗證 Windows 上 `extra_settings` 包含 `WasapiSettings(auto_convert=True)`（對應 WASAPI auto_convert on Windows 情境）。
- [x] [P] 3.2 在 `tests/test_audio_capture.py` 新增測試案例：驗證非 Windows 上 `extra_settings` 為 `None`（對應 Non-Windows platform 情境）。
- [x] [P] 3.3 在 `tests/test_audio_capture.py` 新增測試案例：驗證 fallback 路徑也正確傳遞 `extra_settings`（對應 Fallback path uses WASAPI auto_convert 情境）。
- [x] [P] 3.4 在 `tests/test_audio_capture.py` 新增測試案例：驗證 `WasapiSettings` 不可用時回退至 `None`（對應 WASAPI auto_convert fallback on non-WASAPI Host API 情境）。
