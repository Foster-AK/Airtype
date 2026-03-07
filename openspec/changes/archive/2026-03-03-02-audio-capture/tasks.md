## 1. 音訊擷取核心

- [x] 1.1 建立 `airtype/core/audio_capture.py`，實作使用 sounddevice InputStream 搭配 callback 模式的 `AudioCaptureService` 類別 — 驗證：音訊串流擷取需求
- [x] 1.2 實作透過 sounddevice query_devices 進行輸入裝置列舉 — 驗證：輸入裝置列舉需求
- [x] 1.3 實作執行時裝置切換：停止目前串流 → 在選定裝置上啟動新串流 — 驗證：執行時裝置切換需求

## 2. 環形緩衝區與 RMS

- [x] 2.1 在 `airtype/utils/audio_utils.py` 中使用 numpy 循環陣列實作環形緩衝區（3 秒 = 16kHz 下 48000 個樣本）— 驗證：音訊資料環形緩衝區需求
- [x] 2.2 在音訊 callback 中實作每幀 RMS 音量計算（512 個樣本）— 驗證：RMS 音量計算需求
- [x] 2.3 實作透過 queue 從 callback 到消費者的執行緒安全音訊幀資料交換 — 驗證：執行緒安全資料交換需求

## 3. 整合與依賴

- [x] 3.1 將 `sounddevice` 與 `numpy` 加入 `pyproject.toml` 依賴
- [x] 3.2 將 AudioCaptureService 設定連接至設定模型的 `voice.input_device`

## 4. 測試

- [x] 4.1 撰寫環形緩衝區的單元測試（累積、溢位）
- [x] 4.2 撰寫 RMS 計算的單元測試（已知訊號 → 預期 RMS 值）
- [x] 4.3 撰寫整合測試：啟動擷取 → 錄製 1 秒 → 停止 → 驗證已接收幀
