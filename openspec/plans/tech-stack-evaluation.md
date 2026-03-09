# Airtype 技術棧評估：如果重來一次，該選 Python 還是其他方案？

> **日期**：2026-03-09
> **狀態**：評估完成

## Context

Airtype 是一款跨平台離線語音即時輸入工具，6 天內完成 v2.0 開發。目前技術棧：Python 3.11+ / PySide6 / sounddevice / ONNX Runtime / PyInstaller。本文評估：如果從零開始，Python 是否仍是最佳選擇。

---

## 結論：Python 仍然是正確的選擇，但有些模組值得用其他語言補強

---

## 一、為什麼 Python 仍然是最佳主力語言

### 1.1 ML/ASR 生態系無可匹敵

Airtype 的核心價值在於語音辨識，而 Python 在 ML 推理生態系的優勢是壓倒性的：

| 套件 | Python 支援程度 | 其他語言支援 |
|------|----------------|-------------|
| **Qwen3-ASR** | 官方 SDK（transformers / OpenVINO Python API） | 無官方 binding |
| **faster-whisper** | 純 Python 介面 | 無 |
| **sherpa-onnx** | C++ 核心，Python binding 最完整 | C++/Java/Swift 可用但文件少 |
| **llama-cpp-python** | Python binding | C++ 原生，Rust binding 社群維護 |
| **onnxruntime** | Python 是一等公民 | C++/C#/Java 可用 |
| **Silero VAD** | PyTorch/ONNX，Python 優先 | ONNX 跨語言可用 |

如果換成 Rust 或 C++，幾乎每個 ASR 引擎都需要自己寫 FFI binding 或用不成熟的社群 binding。光這一點就足以讓 Python 成為唯一合理的選擇。

### 1.2 開發速度與 Spec-Driven Development 的契合

6 天完成 15K 行源碼 + 15K 行測試 + 42 份規格 + 50 個變更——這個速度在 Rust/C++ 中幾乎不可能達成。Python 的動態型別 + 豐富套件 + 快速迭代特性，正好匹配 SDD 流程中「快速驗證設計假設」的需求。

### 1.3 PySide6 是「夠好」的跨平台 GUI 方案

- 浮動膠囊不搶焦點（`Qt.Tool` + `WA_ShowWithoutActivating`）——Qt 原生支援
- `QPropertyAnimation` 驅動的波形動畫——效能足夠
- 系統匣圖示——跨平台一致
- 與 Python 核心無縫整合，不需要 IPC

---

## 二、Python 的痛點與替代方案取捨

### 2.1 打包體積過大（400–600MB）

PyInstaller onedir 包含完整的 Python runtime + Qt + numpy + onnxruntime。

**替代方案考量：**

| 方案 | 預期體積 | 問題 |
|------|---------|------|
| **Tauri（Rust + Web UI）** | 10–30MB（不含模型） | Web UI 做「不搶焦點的浮動膠囊」非常困難，跨平台 overlay 行為不一致 |
| **Electron** | 150MB+ | 體積更大，效能更差 |
| **Flutter** | 20–50MB | GUI 層很好，但 ML 推理需全部走 FFI，開發成本高 |

→ 體積問題的根源不是 Python，而是 onnxruntime / Qt / numpy 本身就大。換語言不會顯著改善。

### 2.2 啟動速度偏慢

Python import 鏈較長，冷啟動可能需要 2–3 秒。

**緩解方式（不需要換語言）：**

- 延遲 import（lazy import）：ASR 引擎按需載入
- 目前架構已有 `idle_unloader.py` 做模型動態卸載，方向正確
- 加入 splash screen 降低使用者感知等待時間

### 2.3 GIL 限制併發效能

音訊擷取 → VAD → ASR → LLM 潤飾的管線涉及多執行緒。

**實際影響有限：**

| 模組 | 執行層 | 受 GIL 影響？ |
|------|--------|--------------|
| sounddevice callback | C 層 | ❌ |
| ONNX Runtime 推理 | C++ 層 | ❌ |
| llama-cpp-python 推理 | C++ 層 | ❌ |
| Python 控制流 / 資料搬運 | Python 層 | ✅（但非瓶頸） |

Python 3.13+ 的 free-threaded mode 可進一步緩解。

### 2.4 型別安全性不足

15K 行程式碼中，Protocol + dataclass 提供了基本的結構化，但缺乏編譯期型別檢查。

**緩解方式：**

- 加入 mypy / pyright strict mode
- 現有的 `@runtime_checkable Protocol` 設計已是良好基礎

---

## 三、如果「一定要換」，唯一值得考慮的方案

### Rust 核心 + Python 膠水層（但不建議）

```
┌─────────────────────────┐
│    Python 層（薄）        │
│  · ASR 引擎調度           │
│  · transformers API      │
│  · 設定管理               │
├─────────────────────────┤
│    Rust 核心（厚）        │
│  · 音訊擷取 + 環形緩衝    │
│  · VAD 狀態機             │
│  · 文字注入               │
│  · 快捷鍵監聽             │
├─────────────────────────┤
│    GUI                   │
│  · egui / iced (Rust)    │
│  或 PySide6 (Python)     │
└─────────────────────────┘
```

| 面向 | 評估 |
|------|------|
| **優點** | 記憶體安全、零成本抽象、打包體積顯著縮小、啟動速度快 |
| **缺點** | 開發速度慢 3–5 倍、ASR 整合全部要自寫 FFI、Rust GUI 生態不成熟（egui/iced 遠不及 Qt）、跨語言除錯困難 |
| **時間估算** | 6 天 → 至少 3–4 週 |

**結論：投入產出比不值得。**

---

## 四、最終建議

### 維持現有方案：Python + PySide6

搭配以下改善措施：

| 改善項目 | 做法 | 預期效果 |
|---------|------|---------|
| **型別安全** | 加入 mypy strict + pre-commit hook | 編譯期錯誤檢查 |
| **啟動速度** | lazy import + splash screen | 感知啟動 < 1 秒 |
| **打包體積** | UPX 壓縮 + 排除未使用模組 | 體積減少 30–40% |
| **效能熱點** | 用 Cython 或 Rust（PyO3）加速特定模組（如音訊預處理） | 關鍵路徑加速 2–5× |
| **CI/CD** | GitHub Actions + pytest + mypy | 持續品質保障 |

---

## 五、總結

Python 不是因為「沒有更好的選擇」才被選中——而是因為在 **ML 推理 + 快速原型 + 跨平台桌面應用** 這個交集中，它就是最佳選擇。

Airtype 的核心競爭力不在語言效能，而在 **ASR 模型的整合品質**和**使用者體驗設計**。Python 讓團隊把精力花在正確的地方。
