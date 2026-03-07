## 背景

Qwen3-ASR 預期以 log-Mel 頻譜特徵作為輸入。參考實作（QwenASRMiniTool）已證明這可以完全以 NumPy 實現，為僅使用 CPU 的使用者消除約 2GB 的 PyTorch 依賴。

相依性：01-project-setup。

## 目標 / 非目標

**目標：**

- 以純 NumPy 實作 Mel 頻譜提取
- 從預先提取的提示模板實作 BPE 分詞
- 內建預先計算的濾波器矩陣與 token 模板
- 輸出與 PyTorch 參考實作一致

**非目標：**

- 不進行音訊檔案格式轉換（輸入始終為來自 sounddevice 的 16kHz PCM）
- 不進行 GPU 加速前處理
- 不支援非 Qwen3-ASR 模型（Breeze/sherpa 有各自的前處理）

## 決策

### 純 NumPy STFT 與 Mel 濾波器組

使用 `numpy.fft.rfft` 搭配 Hanning 視窗實作短時傅立葉變換。應用來自 `mel_filters.npy` 的預先計算 Mel 濾波器組。轉換為 log-Mel：`np.log10(np.maximum(mel_spec, 1e-10))`。

**為何不使用 scipy.signal.stft**：避免 scipy 依賴。NumPy FFT 已足夠且最佳化良好。

### 預先計算的 mel_filters.npy 與 prompt_template.json

`mel_filters.npy` 包含 128 頻帶 Mel 濾波器矩陣（從 Qwen3-ASR 模型設定一次性產生）。`prompt_template.json` 包含預先提取的 BPE 提示 token ID。兩者皆內建於 `models/precomputed/`。

**為何預先計算**：避免執行時依賴 transformers 分詞器與模型設定載入。一次性產生，隨應用程式發佈。

### 從模板實作 BPE 分詞器

BPE 提示 token 以整數陣列形式預先提取於 `prompt_template.json`。前處理器僅需載入並前置這些 token。執行時無需分詞器函式庫。

## 風險 / 取捨

- [風險] NumPy 與 PyTorch FFT 之間的數值精度差異 → 緩解措施：以容差 < 1e-4 驗證輸出與 PyTorch 參考一致（與 spec 一致）
- [取捨] 內建的 .npy 檔案依模型版本而異 → 可接受；模型版本變更時重新產生
