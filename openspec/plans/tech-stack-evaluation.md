# Airtype 架構重新評估：回到第一原則

> **日期**：2026-03-09
> **狀態**：評估完成（v2，納入 Qwen3-ASR 精度優勢和 macOS 平台定位修正）

## Context

Airtype v2.0 在 6 天內完成了 15,203 行源碼 + 15,095 行測試，支援 5 種 ASR 引擎、3 種 GPU 推理路徑、本機 LLM 潤飾。開發者反思後認為：**專案最大的問題不是「選錯語言」，而是「太貪心」**。支援太多引擎導致複雜度指數級成長，而實際上所有模型都跑在 CPU/ONNX 上就夠了。

本評估從第一原則出發：我們到底在解決什麼問題？面對什麼使用者？什麼才是最佳方案？

---

## 一、問題本質分析

### 1.1 Airtype 到底在解決什麼問題？

**一句話：讓使用者在任何應用中，按一個快捷鍵就能用語音輸入文字，不需要網路。**

這是一個「輸入法」問題，不是一個「AI 平台」問題。使用者不在乎底層跑的是 Qwen3 還是 SenseVoice——他們在乎的是：
- 按下去能不能用？（可靠性）
- 辨識的準不準？（準確度）
- 等多久？（延遲）
- 會不會打斷我的工作？（不搶焦點）

### 1.2 真正的使用者是誰？

PRD 定義了三類使用者，但 80% 的價值集中在一類：

> **台灣的知識工作者**：每天大量中文輸入，在 IDE / 文件 / 通訊軟體間切換，需要一個「不干擾」的語音輸入工具。

**他們的平台特徵（基於市場數據）：**

根據 Stack Overflow 2024 開發者調查，macOS 在專業開發者中佔 **33.2%**，遠高於一般消費市場的 15%。在台灣的知識工作者（軟體工程師、寫作者、研究人員）中，MacBook 的使用比例更高——走進台北的咖啡廳、科技公司或共享空間，MacBook 的出現頻率顯著高於一般桌面統計。

**→ macOS 應被視為與 Windows 同等重要的平台，而非「次要」。**

他們的硬體特徵：
- macOS 與 Windows 並重（知識工作者 Mac 比例遠高於一般消費者）
- 大多沒有獨立 GPU（MacBook / 辦公筆電）
- Apple Silicon (M1-M4) 成為 Mac 主流，CPU 推理效能強
- RAM 通常 8-16GB（Mac 統一記憶體架構效率更高）
- 不想安裝 Python、不想管依賴、只要能用

**他們最在乎的：辨識準確度。** 文字工作者每天輸入數千字，如果 ASR 辨識率不夠高，頻繁修正錯字的體驗會比打字更差。準確度是決定產品能否留住使用者的第一要素。

### 1.3 什麼是 MVP？什麼是 nice-to-have？

| 分類 | 功能 | 現狀 |
|------|------|------|
| **MVP 必要** | 快捷鍵觸發 → 語音輸入 → 文字注入 | ✅ |
| **MVP 必要** | 1 個夠好的 ASR 引擎（繁中 + 英文） | ❌ 有 5 個 |
| **MVP 必要** | 浮動膠囊 UI（不搶焦點） | ✅ |
| **MVP 必要** | VAD 自動偵測語音起止 | ✅ |
| **MVP 必要** | 離線運作 | ✅ |
| **Nice-to-have** | 多 ASR 引擎切換 | ❌ 過度設計 |
| **Nice-to-have** | GPU 加速（CUDA / Vulkan / OpenVINO） | ❌ 過度設計 |
| **Nice-to-have** | LLM 潤飾 | 可選外掛 |
| **Nice-to-have** | 自訂辭典 / 熱詞 | 第二階段 |
| **Nice-to-have** | 52 種語言支援 | 第三階段 |
| **Nice-to-have** | 4 種 UI 語言 | 第二階段 |

---

## 二、v2.0 的複雜度量化分析

### 2.1 多引擎帶來的代價

```
直接的 ASR 引擎程式碼：
  asr_qwen_openvino.py     724 行
  asr_engine.py（抽象層）   568 行
  asr_qwen_vulkan.py       463 行
  asr_sherpa.py             426 行
  asr_qwen_pytorch.py      418 行
  asr_breeze.py             354 行
  asr_utils.py               29 行
  ──────────────────────────────
  小計                     2,982 行

因多引擎衍生的基礎設施：
  hardware_detect.py        583 行（GPU 偵測邏輯）
  model_manager.py          841 行（多模型下載管理）
  settings_models.py        656 行（模型管理 UI）
  settings_voice.py         462 行（多引擎切換 UI）
  pipeline.py 中的分支邏輯   ~200 行（估計）
  ──────────────────────────────
  小計                     2,742 行

對應測試（估計 1:1）:     ~5,700 行

對應 spec 文件：             5 份
optional dependencies：      4 組
打包體積增量：            ~200MB
```

**總計：多引擎支援佔了整個專案 ~38% 的程式碼量（~5,700 / 15,200 行）。**

如果只保留 1 個引擎，專案可以從 15,200 行縮減到 ~9,500 行，複雜度降低近 40%。

### 2.2 GPU 加速帶來的代價

- `asr_qwen_pytorch.py`（418 行）：CUDA 推理
- `asr_qwen_vulkan.py`（463 行）：Vulkan 推理
- `hardware_detect.py`（583 行）：GPU 偵測（NVIDIA / AMD / Intel）
- 打包腳本中 CUDA variant 的處理
- pyproject.toml 中 torch / openvino 的可選依賴

**而實際上，所有使用者最終都用 CPU 推理。** Qwen3-ASR 0.6B INT8 在 CPU 上已經可以在 2-3 秒內完成辨識。GPU 加速是一個「理論上有用但實際不需要」的功能。

---

## 三、簡化後的理想架構

### 3.1 ASR 引擎選擇：準確度優先

**核心原則：對文字工作者來說，辨識準確度是留存率的第一決定因素。**

每修正一個錯字就是一次工作流中斷。如果使用者覺得「還不如自己打字」，產品就失敗了。因此，ASR 引擎的選擇必須以準確度為第一優先。

#### Qwen3-ASR 的壓倒性精度優勢（基於公開基準測試）

| 基準測試（中文） | Qwen3-ASR-1.7B | Qwen3-ASR-0.6B | Whisper-large-v3 | GPT-4o-Transcribe |
|----------------|---------------|---------------|-----------------|-------------------|
| WenetSpeech | **4.97** | 5.88 | 9.86 | 15.30 |
| 老幼語音 | **3.81** | 4.48 | 4.17 | 14.27 |
| 極端噪音 | **16.17** | 17.88 | 17.04 | 36.11 |
| 對話場景 | **6.54** | 7.06 | 6.61 | 20.73 |
| 繞口令 | **2.44** | 4.06 | 3.47 | 20.87 |

> 來源：[Qwen3-ASR Technical Report (arXiv:2601.21337)](https://arxiv.org/abs/2601.21337)

**Qwen3-ASR-1.7B 在中文 WER 上比 Whisper-large-v3 好 ~50%，比 GPT-4o-Transcribe 好 ~70%。** 即使是輕量版 0.6B，精度也與 Whisper-large-v3 相當甚至更好。

相比之下，sherpa-onnx 支援的模型（SenseVoice-Small、Paraformer-zh）雖然體積小、速度快，但精度明顯低於 Qwen3-ASR。對於每天輸入數千字的知識工作者，這個差距會直接影響使用體驗。

#### Qwen3-ASR 的部署挑戰

| 面向 | 現狀 |
|------|------|
| ONNX 匯出 | ❌ 尚無官方 ONNX 匯出 |
| sherpa-onnx 支援 | ❌ 尚未整合 |
| 輕量 CPU 推理 | ❌ 目前需要 PyTorch 或 vLLM |
| Apple Silicon 原生 | ⚠️ PyTorch 支援 MPS，但非最佳化 |

**這是核心矛盾：最好的模型需要最重的依賴。**

#### 建議方案：Qwen3-ASR 0.6B 作為唯一引擎（接受 PyTorch 依賴）

```
策略：用 1 個好引擎 + PyTorch 依賴
      取代 5 個引擎 + 5 套依賴
```

**理由：**
1. **精度不可妥協** — 這是產品的核心價值主張
2. **Qwen3-ASR 0.6B 在 CPU 上可用** — PyTorch CPU 後端推理 ≤ 3 秒
3. **依賴雖重但單一** — 1 個 PyTorch 比 openvino + faster-whisper + sherpa-onnx + torch 四套加起來簡單
4. **Apple Silicon 友好** — PyTorch MPS 後端對 M1-M4 支援良好
5. **未來路線清晰** — 等 ONNX 匯出成熟後再遷移到更輕量的方案

**與 v2.0 的差別：**
- v2.0：5 個引擎（Qwen3 OpenVINO + Qwen3 PyTorch CUDA + Qwen3 Vulkan + Breeze + sherpa-onnx）
- 建議：1 個引擎（Qwen3-ASR 0.6B，僅 PyTorch CPU + MPS）
- 移除的：OpenVINO、CUDA、Vulkan、faster-whisper、sherpa-onnx
- 複雜度降低：從 5 套推理路徑 → 1 套

### 3.2 移除 GPU 加速架構

- 刪除 `asr_qwen_pytorch.py` 中的 CUDA 路徑（保留 CPU + MPS）
- 刪除 `asr_qwen_vulkan.py`（整個移除）
- 大幅簡化 `hardware_detect.py`（只需偵測 CPU 核心數、RAM、是否 Apple Silicon）
- 移除 openvino / CUDA 相關依賴
- 打包體積：PyTorch CPU-only wheel 約 200MB（不含 CUDA runtime 的 2GB+）

### 3.3 LLM 潤飾改為可選外掛

現狀：LLM 潤飾（llama-cpp-python + GGUF 模型）內建在核心中，但 PRD 預設就是關閉的（`啟用 AI 潤飾: OFF`）。

建議：
- 核心不包含 LLM
- 提供獨立的「AI 潤飾外掛」，使用者手動安裝
- 或直接支援 Ollama API（使用者自行安裝 Ollama），零額外依賴

### 3.4 未來遷移路線：等待 Qwen3-ASR ONNX 化

```
現在（2026 Q1）               未來（等 ONNX 匯出成熟）
─────────────────────         ─────────────────────────
Qwen3-ASR 0.6B                Qwen3-ASR 0.6B
+ PyTorch CPU/MPS      →      + ONNX Runtime（或 sherpa-onnx）
依賴：~200MB PyTorch           依賴：~50MB onnxruntime
打包：~350MB                   打包：~200MB
```

當社群或官方提供 Qwen3-ASR 的 ONNX 匯出後，可以無縫遷移到 onnxruntime，大幅降低依賴體積。這個遷移不需要改變上層架構——只需替換推理後端。

---

## 四、技術棧重新評估

### 4.1 Python 仍然是正確選擇嗎？

**是的，而且選擇 Qwen3-ASR 後理由更強了。**

Qwen3-ASR 官方推理框架基於 Python（PyTorch / vLLM）。目前沒有 C++ / Rust 的獨立推理方案。選擇 Qwen3-ASR 等同於選擇 Python。

Python 的核心優勢：
1. **Qwen3-ASR 官方 SDK 就是 Python** — 這是唯一的推理路徑
2. **PySide6 做浮動膠囊 UI 沒有更好的替代品** — 不搶焦點、跨平台一致
3. **開發速度** — 一人專案，快速迭代比效能重要
4. **sounddevice + pynput + pyperclip** — 這些「膠水工具」在 Python 中最方便

### 4.2 是否有更激進的方案？

**方案 B：等 ONNX 匯出後用 C++ / Qt**

如果未來 Qwen3-ASR 支援 ONNX 匯出，理論上可以用 C++ + Qt + onnxruntime 做一個完全不依賴 Python 的版本。但這是「未來式」，目前不可行。

**結論：Python 是目前唯一務實的選擇，這不是偏好問題，而是 Qwen3-ASR 的技術限制決定的。**

### 4.3 GUI 框架評估

| 框架 | 不搶焦點浮動窗 | 系統匣 | 跨平台一致 | 打包體積 | 與 Python 整合 |
|------|--------------|--------|----------|---------|--------------|
| **PySide6** ✅ | ✅ 原生 | ✅ | ✅ | ~80MB | 原生 |
| Tauri | ⚠️ 困難 | ✅ | ⚠️ | ~5MB | ❌ 需 IPC |
| Electron | ⚠️ 困難 | ✅ | ✅ | ~150MB | ❌ 需 IPC |
| tkinter | ❌ 受限 | ❌ | ⚠️ | 內建 | 原生 |
| Dear ImGui | ✅ | ❌ | ⚠️ | ~5MB | 需 binding |

**PySide6 仍然是最佳選擇**。「不搶焦點的浮動膠囊」是核心 UX，這一點 Qt 做得最好。

---

## 五、推薦的最小技術棧

### 5.1 架構圖

```
┌──────────────────────────────────────────┐
│              Airtype Lite                │
├──────────────────────────────────────────┤
│  UI 層（PySide6）                        │
│  · 浮動膠囊 + 音波圖                     │
│  · 系統匣圖示                            │
│  · 設定視窗（3 頁：一般 / 語音 / 關於）    │
├──────────────────────────────────────────┤
│  核心層                                  │
│  · CoreController（狀態機，保留）          │
│  · AudioCapture（sounddevice，保留）      │
│  · VadEngine（Silero VAD ONNX，保留）     │
│  · ASR（Qwen3-ASR 0.6B，唯一引擎）       │
│  ·   └─ PyTorch CPU / MPS 推理           │
│  · TextInjector（pyperclip，保留）        │
│  · HotkeyManager（pynput，保留）          │
├──────────────────────────────────────────┤
│  工具層                                  │
│  · ConfigManager（簡化，移除多引擎欄位）    │
│  · ModelManager（簡化，只管 1 個 ASR 模型） │
│  · i18n（保留但初始只支援繁中 + 英文）      │
├──────────────────────────────────────────┤
│  可選外掛（不在核心中）                    │
│  · LLM 潤飾（Ollama API）                │
│  · 辭典管理                               │
└──────────────────────────────────────────┘
```

### 5.2 依賴清單

```toml
[project]
dependencies = [
    "PySide6>=6.6",
    "sounddevice>=0.4.7",
    "numpy>=1.26",
    "onnxruntime>=1.17",    # VAD（Silero）推理
    "torch>=2.0",           # Qwen3-ASR 推理（CPU-only wheel）
    "transformers>=4.40",   # Qwen3-ASR 模型載入
    "pynput>=1.7",
    "pyperclip>=1.8",
    "pyautogui>=0.9.54",
    "psutil>=5.9",
]

[project.optional-dependencies]
llm = ["httpx>=0.27"]      # Ollama API 呼叫
dev = ["pytest>=8.0"]
```

**關鍵改變：**
- 保留 `torch` + `transformers`（Qwen3-ASR 必要）
- 但使用 **CPU-only torch wheel**（~200MB，非 CUDA 版的 2GB+）
- 移除 openvino、faster-whisper、sherpa-onnx、llama-cpp-python
- 從 5 套推理框架 → 1 套（PyTorch CPU/MPS）

### 5.3 預估程式碼量

| 模組 | v2.0 行數 | Lite 預估 | 變化 |
|------|----------|----------|------|
| core/ | ~5,500 | ~2,800 | -49%（移除 4 個 ASR 引擎 + GPU 路徑 + 簡化 pipeline） |
| ui/ | ~4,500 | ~2,200 | -51%（移除模型管理 UI + 簡化設定頁） |
| utils/ | ~3,200 | ~1,200 | -63%（大幅簡化 hardware_detect + model_manager） |
| tests/ | ~15,000 | ~6,200 | -59% |
| **總計** | **~30,300** | **~12,400** | **-59%** |

### 5.4 打包體積預估

| 組件 | v2.0 | Lite |
|------|------|------|
| Python runtime | ~30MB | ~30MB |
| PySide6 | ~80MB | ~80MB |
| onnxruntime | ~50MB | ~50MB |
| torch (CPU-only) | — | ~200MB |
| transformers | — | ~30MB |
| openvino / faster-whisper / sherpa-onnx | ~200MB | 0 |
| 其他依賴 | ~40MB | ~10MB |
| **程式總計（不含模型）** | **~400MB** | **~400MB** |
| 預設模型 | 多模型 ~2GB | Qwen3-ASR 0.6B ~1.2GB |
| **最終安裝大小** | **~600MB+** | **~400MB + 1.2GB 模型** |

> **注意：** 選擇 Qwen3-ASR 意味著打包體積無法大幅縮減（PyTorch CPU wheel 本身就 ~200MB）。但複雜度大幅降低——從 5 套推理框架的排列組合 → 1 套清晰的路徑。**體積不變，但架構變簡單了。**
>
> **未來 ONNX 化後**，可用 onnxruntime 取代 torch + transformers，體積可降至 ~200MB。

---

## 六、開發策略建議

### 6.1 分階段交付

```
Phase 1（MVP，2 週）：
  快捷鍵 → 音訊 → VAD → Qwen3-ASR 0.6B → 文字注入
  浮動膠囊 UI + 系統匣
  基本設定（麥克風選擇、快捷鍵）
  macOS + Windows 打包（macOS 優先，知識工作者主力平台）

Phase 2（增強，1 週）：
  自訂辭典 / 替換規則
  LLM 潤飾外掛（Ollama API）
  i18n（繁中 + 英文）

Phase 3（最佳化，按需）：
  等待 Qwen3-ASR ONNX 匯出 → 遷移到 onnxruntime（降低體積）
  更多語言支援
  Linux 支援
```

### 6.2 開發實踐改善（來自 DEV_RETROSPECTIVE.md）

- 每完成一個功能就提交一次（不再巨型 commit）
- 先跑 UI 看效果，再寫測試（避免 25 個 UI bug 集中爆發）
- 設定 CI（GitHub Actions + pytest）
- 用 `.gitattributes` 統一換行符

---

## 七、總結

| 面向 | v2.0（太貪心） | 建議的 Lite 版 |
|------|--------------|---------------|
| ASR 引擎 | 5 個 | 1 個（**Qwen3-ASR 0.6B**） |
| 推理框架 | 5 套（OpenVINO / PyTorch CUDA / Vulkan / faster-whisper / sherpa-onnx） | 1 套（PyTorch CPU/MPS） |
| GPU 支援 | 3 種（CUDA / Vulkan / OpenVINO） | 無（純 CPU + Apple Silicon MPS） |
| LLM 潤飾 | 內建（llama-cpp-python） | 可選外掛（Ollama API） |
| 設定頁面 | 7 頁 | 3 頁 |
| 主要平台 | Windows 優先 | **macOS + Windows 並重** |
| 源碼行數 | ~15,200 | ~6,200（-59%） |
| 依賴套件 | 14 個核心 + 9 個可選 | 10 個核心 + 1 個可選 |
| 開發時間 | 6 天（但過於緊湊） | Phase 1: 2 週（穩健） |
| 語言 | Python ✅ | Python ✅（不變） |
| GUI | PySide6 ✅ | PySide6 ✅（不變） |

### 三個核心決策

1. **ASR 引擎：只留 Qwen3-ASR 0.6B** — 中文 WER 比 Whisper-large-v3 好 ~50%，準確度是留存率的決定因素。文字工作者無法容忍頻繁修正錯字。

2. **移除 GPU 架構** — Qwen3-ASR 0.6B CPU 推理 ≤ 3 秒已足夠。CUDA / Vulkan / OpenVINO 三套 GPU 路徑帶來了 38% 的程式碼量但幾乎沒有使用者受益。

3. **LLM 改為外掛** — 預設就是關閉的功能不應該內建。透過 Ollama API 支援即可，零額外依賴。

### 核心洞察

**問題從來不是「選錯語言」，而是「做太多」。**

Python + PySide6 + Qwen3-ASR 是這個問題域的最佳技術棧。將 5 個引擎收斂到 1 個、移除 GPU 架構、將 LLM 改為外掛——這三個決策就能砍掉 59% 的程式碼，讓專案回到可維護的規模。

打包體積不會因此大幅縮減（PyTorch 本身就大），但**架構複雜度**從指數級降到線性。未來等 Qwen3-ASR ONNX 匯出成熟後，體積也能進一步壓縮。

---

## 參考資料

- [Qwen3-ASR Technical Report (arXiv:2601.21337)](https://arxiv.org/abs/2601.21337)
- [Qwen3-ASR GitHub Repository](https://github.com/QwenLM/Qwen3-ASR)
- [Best Open Source STT Model in 2026 (Northflank Benchmarks)](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [Qwen3-ASR Swift: On-Device ASR for Apple Silicon](https://blog.ivan.digital/qwen3-asr-swift-on-device-asr-tts-for-apple-silicon-architecture-and-benchmarks-27cbf1e4463f)
- [sherpa-onnx GitHub Repository](https://github.com/k2-fsa/sherpa-onnx)
