## 1. Mel 頻譜

- [x] 1.1 建立 `airtype/core/processor_numpy.py`，實作純 NumPy STFT 與 Mel 濾波器組用於頻譜提取（Hanning 視窗、numpy.fft.rfft、128 Mel 頻帶）— 驗證：Mel 頻譜提取需求
- [x] 1.2 將預先計算的 mel_filters.npy 與 prompt_template.json 檔案內建於 `models/precomputed/`，搭配載入邏輯 — 驗證：預先計算的 Mel 濾波器組需求

## 2. BPE 分詞

- [x] 2.1 實作從模板載入的 BPE 分詞器：載入 `models/precomputed/prompt_template.json`、將 token ID 前置於模型輸入 — 驗證：BPE 提示分詞需求
- [x] 2.2 內建 `models/precomputed/prompt_template.json` 佔位檔案（實際 token 從模型設定產生）

## 3. 驗證

- [x] 3.1 撰寫數值精度測試：比較 NumPy 輸出與已知參考值，容差 < 1e-4 — 驗證：數值精度需求
- [x] 3.2 撰寫測試驗證無 PyTorch 依賴：匯入 processor_numpy 後斷言 torch 不在 sys.modules 中
