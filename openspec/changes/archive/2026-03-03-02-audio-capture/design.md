## 背景

Airtype 需要來自麥克風的即時音訊以供 VAD 和 ASR 使用。PRD 指定 sounddevice（PortAudio）為音訊框架，16kHz 單聲道 PCM，512 樣本緩衝區。此為基礎 I/O 層。

相依性：01-project-setup（設定、日誌記錄）。

## 目標 / 非目標

**目標：**

- 從任何系統麥克風擷取 16kHz 單聲道音訊
- 列舉並在執行時切換輸入裝置
- 提供環形緩衝區用於音訊資料累積
- 計算每幀 RMS 供波形 UI 使用

**非目標：**

- 不進行 VAD 處理（屬於 03-vad-engine）
- 不進行音訊播放或錄製至檔案
- 不進行降噪（RNNoise 為設定功能，延後處理）

## 決策

### sounddevice InputStream 搭配 callback 模式

使用 `sounddevice.InputStream` 搭配接收音訊區塊的 callback 函式。callback 在 PortAudio 背景執行緒中執行，因此必須輕量——僅複製資料至環形緩衝區並計算 RMS。

**為何選擇 callback 而非阻塞式讀取**：callback 避免阻塞主執行緒，並提供一致的低延遲音訊傳遞。

### 使用 numpy 循環陣列實作環形緩衝區

實作固定大小的循環緩衝區（3 秒 = 16kHz 下 48000 個樣本），使用帶有 head/tail 指標的 numpy 陣列。這避免了擷取期間的記憶體配置。

**為何不使用 collections.deque**：numpy 陣列允許零複製切片供 ASR 輸入使用，且對音訊資料更節省記憶體。

### 透過 sounddevice query_devices 進行裝置列舉

使用 `sounddevice.query_devices(kind='input')` 列出可用輸入裝置。將選定的裝置索引儲存於設定中（`voice.input_device`）。支援 "default" 作為特殊值。

### 透過 queue 實現執行緒安全資料交換

音訊幀由 callback 放入 `queue.Queue` 供消費者（VAD、ASR）讀取。RMS 值使用另一個輕量機制（原子浮點數或小型 queue）。

## 風險 / 取捨

- [風險] sounddevice/PortAudio 在某些 Linux 音訊設定（PulseAudio/PipeWire/ALSA 衝突）上可能失敗 → 緩解措施：記錄包含裝置資訊的詳細錯誤；退回至預設裝置
- [風險] callback 執行緒不得阻塞 → 緩解措施：callback 中僅進行 numpy 複製 + RMS；所有繁重處理在消費者執行緒中進行
- [取捨] 3 秒環形緩衝區限制處理前的最大語音擷取長度 → 可接受：VAD 在此時間窗口內觸發 ASR；較長音訊由 ASR 自身的緩衝區累積
