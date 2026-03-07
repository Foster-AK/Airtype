## 為什麼

ASR 管線需要知道使用者何時說話、何時靜默。VAD（語音活動偵測）決定語音邊界、觸發 ASR 處理，並在靜默後啟用自動停止。沒有 VAD，系統無法自動偵測何時開始/停止辨識。

參考：PRD §6.2（VAD 引擎）、§8.1（狀態機 — SPEAKING/SILENCE_COUNTING 狀態）。

相依性：01-project-setup、02-audio-capture。

## 變更內容

- 在 `airtype/core/vad.py` 中實作封裝 Silero VAD v5（ONNX）的 `VadEngine`
- 實作 VAD 狀態機：IDLE → SPEECH → SILENCE_COUNTING → SPEECH_ENDED
- 處理 512 樣本（32ms）幀，可設定語音門檻值（預設 0.5）
- 可設定靜默逾時（0.5s–5.0s，預設 1.5s）用於自動停止
- 發出狀態轉換事件供核心控制器使用

## 功能

### 新增功能

- `vad-engine`：使用 Silero VAD 的語音活動偵測，搭配用於語音邊界偵測的狀態機

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/vad.py`、`tests/test_vad.py`
- 新增依賴：`onnxruntime`
- 內建模型：`models/vad/silero_vad_v5.onnx`（約 2MB）
- 相依：01-project-setup、02-audio-capture（音訊幀）
