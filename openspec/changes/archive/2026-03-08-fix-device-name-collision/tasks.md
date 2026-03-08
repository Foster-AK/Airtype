## 1. 設定資料模型修改

- [x] [P] 1.1 修改 `airtype/config.py`：Config 欄位型別擴展為 Union，將 `VoiceConfig.input_device` 從 `str` 改為 `str | int`（設定資料模型）。驗證：`VoiceConfig(input_device=41)` 可建立且 `to_dict()` → `from_dict()` round-trip 保持 int 型別（Integer device index round-trip）。

## 2. UI 裝置選擇元件（以裝置 index 取代裝置名稱作為識別值）

- [x] [P] 2.1 修改 `airtype/ui/device_selector.py`：以裝置 index 取代裝置名稱作為識別值，`addItem` 的 itemData 改存 `d["index"]`（int），Signal 型別改為 object（Device selection stores index、Voice Settings Page）。驗證：DeviceSelector 選擇裝置後 emit 的值為 int。

- [x] [P] 2.2 修改 `airtype/ui/settings_voice.py`：`_refresh_devices` 的 `addItem` itemData 改存 `d["index"]`，`_on_device_changed` 取出 int，Signal 型別改為 object，`_MicTestWorker.__init__` 的 `device` 參數型別改為 `str | int`（Voice Settings Page、Test Microphone）。驗證：設定面板選擇麥克風後 `config.voice.input_device` 為 int；麥克風測試以 int index 開啟串流。

## 3. Audio Stream Capture fallback

- [x] 3.1 修改 `airtype/core/audio_capture.py` 的 `start()` 方法：新增裝置 index 無效時的 fallback，當以 int index 開啟 `sd.InputStream` 失敗時，catch 異常、log 警告、退回 `device=None`（系統預設）重試（Audio Stream Capture、Start capture with invalid device index）。驗證：傳入不存在的 device index 時不拋異常，改用預設裝置啟動。

## 4. 測試

- [x] 4.1 新增或更新 `tests/test_audio_capture.py` 測試：驗證 int index 開啟串流、invalid index fallback、`"default"` 正常運作。執行 `python -m pytest tests/` 全部通過。
