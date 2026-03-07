## 為什麼

ASR 管線需要來自使用者麥克風的即時音訊輸入。此變更使用 sounddevice（PortAudio）實作音訊擷取層，包含裝置列舉、用於連續擷取的環形緩衝區，以及供 UI 回饋使用的 RMS 音量計算。此為 VAD（03）和辨識管線（12）的前置需求。

參考：PRD §6.1（音訊擷取引擎）、§3.2（音訊擷取模組）。

相依性：01-project-setup。

## 變更內容

- 使用 sounddevice 在 `airtype/core/audio_capture.py` 中實作 `AudioCaptureService`
- 支援 16kHz 單聲道 PCM 擷取，512 樣本（32ms）緩衝區
- 列舉可用輸入裝置並允許執行時切換
- 實作 3 秒環形緩衝區用於音訊資料
- 計算每幀 RMS 音量供波形視覺化使用
- 提供開始/停止/暫停控制與裝置熱插拔（無需重啟）

## 功能

### 新增功能

- `audio-capture`：即時麥克風音訊擷取，包含裝置管理、環形緩衝區與 RMS 計量

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/audio_capture.py`、`airtype/utils/audio_utils.py`、`tests/test_audio_capture.py`
- 新增依賴：`sounddevice`、`numpy`
- 相依：01-project-setup（設定模型、日誌記錄）
