## 為什麼

Qwen3-ASR 需要 Mel 頻譜提取與 BPE 分詞作為前處理。以純 NumPy 實作（無 PyTorch/torchaudio 依賴）可大幅縮小部署大小與啟動時間，這對「開箱即用」的體驗至關重要，尤其是 OpenVINO INT8 CPU 路徑。

參考：PRD §6.3.6（音訊前處理管線）、QwenASRMiniTool 的 `processor_numpy.py` 架構。

相依性：01-project-setup。

## 變更內容

- 實作純 NumPy Mel 頻譜提取（STFT → 幅度 → Mel 濾波器 → log-Mel）
- 使用預先提取的提示模板實作 BPE 分詞器
- 內建預先計算的 `mel_filters.npy` 與 `prompt_template.json`
- 前處理不依賴 PyTorch、torchaudio 或 transformers

## 功能

### 新增功能

- `numpy-preprocessor`：Qwen3-ASR 的純 NumPy 音訊前處理（不依賴 PyTorch 的 Mel 頻譜與 BPE 分詞）

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/processor_numpy.py`、`tests/test_preprocessor.py`
- 新增內建資料：`models/precomputed/mel_filters.npy`、`models/precomputed/prompt_template.json`
- 依賴：`numpy`（已在 02 中加入）
- 相依：01-project-setup
