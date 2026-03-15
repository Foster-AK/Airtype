# Airtype 安裝與打包指南

## 目錄

- [開發環境安裝](#開發環境安裝)
- [從原始碼執行](#從原始碼執行)
- [打包建置](#打包建置)
  - [Windows](#windows)
  - [macOS](#macos)
  - [Linux](#linux)
- [產出檔案](#產出檔案)
- [模型下載](#模型下載)
- [FAQ（常見問題）](#faq常見問題)

---

## 開發環境安裝

### 系統需求

- Python 3.11 或以上
- 作業系統：Windows 10/11、macOS 12+、Linux（X11）

### 安裝步驟

```bash
# 1. 複製專案
git clone <repo-url> && cd Airtype

# 2. 建立虛擬環境（建議）
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. 安裝核心依賴
pip install -e .

# 4. 安裝完整依賴（含所有 ASR 引擎 + LLM）
pip install -e ".[full]"

# 5.（可選）安裝開發工具
pip install -e ".[dev]"
```

### 選擇性安裝

若不需要全部功能，可以只安裝特定引擎：

| 引擎 | 安裝指令 | 說明 |
|------|---------|------|
| Breeze-ASR | `pip install -e ".[breeze]"` | faster-whisper + transformers |
| sherpa-onnx | `pip install -e ".[sherpa]"` | SenseVoice / Paraformer 輕量推理 |
| LLM 潤飾 | `pip install -e ".[llm]"` | llama-cpp-python 本機 LLM |

> **注意**：核心 ASR 引擎（Qwen3-ASR ONNX）已包含在基本安裝中，不需額外安裝。

#### llama-cpp-python GPU 加速（可選）

```bash
# CUDA GPU
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124 --prefer-binary

# CPU only（預設）
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary
```

---

## 從原始碼執行

```bash
python -m airtype
```

設定檔位於 `~/.airtype/config.json`，首次執行會自動建立。

---

## 打包建置

打包使用 PyInstaller，採用**目錄模式（onedir）**，產出一個包含執行檔與所有依賴的目錄。

### 共通前置作業

```bash
pip install -e ".[packaging]"
```

> **重要**：打包時**不要**使用 `pip install -e ".[full]"`！`[full]` 會安裝 PyTorch、transformers 等巨型套件，
> 導致打包體積膨脹至 2GB+。`[packaging]` 只安裝核心功能 + tokenizers + PyInstaller，
> 打包體積約 250-350MB。建議使用建置腳本（會自動建立乾淨 venv）。

### Windows

```batch
build\build_windows.bat [cpu|cuda|both|skip]
```

- 參數控制 llama-cpp-python 的安裝版本，不帶參數會互動式詢問
- 產出：`dist\airtype\airtype.exe`
- 若已安裝 [NSIS](https://nsis.sourceforge.io/)，腳本會自動呼叫 `makensis` 建立安裝程式 `dist\AirtypeSetup-0.1.0-win64.exe`

#### 手動打包

```bash
pyinstaller airtype.spec --clean --noconfirm
```

### macOS

```bash
bash build/build_macos.sh
```

- 產出：`dist/airtype/Airtype.app` + DMG 安裝映像
- 程式碼簽署（可選）：設定環境變數 `CODESIGN_IDENTITY`
- 公證（可選）：額外設定 `NOTARIZE_APPLE_ID`、`NOTARIZE_TEAM_ID`、`NOTARIZE_PASSWORD`
- 建立精美 DMG 需安裝 `brew install create-dmg`

### Linux

```bash
bash build/build_linux.sh
```

- 產出：`dist/airtype-0.1.0-x86_64.AppImage`
- 需要 `appimagetool`（腳本會自動下載）
- 架構可透過環境變數 `ARCH` 指定（預設 `x86_64`）

---

## 產出檔案

| 平台 | 執行檔 | 安裝程式 |
|------|--------|---------|
| Windows | `dist\airtype\airtype.exe` | `dist\AirtypeSetup-0.1.0-win64.exe` |
| macOS | `dist/airtype/Airtype.app` | `dist/AirtypeInstaller-0.1.0-macOS.dmg` |
| Linux | `dist/airtype/airtype` | `dist/airtype-0.1.0-x86_64.AppImage` |

---

## 模型下載

首次執行 Airtype 後，在「設定 → 模型管理」頁面下載所需模型。

### ASR 語音辨識模型

| 模型 | 大小 | 推理引擎 | 說明 |
|------|------|---------|------|
| Qwen3-ASR 1.7B ONNX INT8 | 3.6 GB | ONNX Runtime CPU | 高品質，CPU 首選 |
| Qwen3-ASR 0.6B ONNX INT8 | 1.2 GB | ONNX Runtime CPU | 輕量快速 |
| SenseVoice Small | 900 MB | sherpa-onnx | 多語言輕量模型 |
| Breeze-ASR-25 | 3.1 GB | faster-whisper | 繁中專精 |

### LLM 文字潤飾模型

| 模型 | 大小 | 說明 |
|------|------|------|
| Qwen2.5-1.5B Q4_K_M | 986 MB | 最輕量，適合低 RAM |
| Qwen2.5-3B Q4_K_M | 1.9 GB | 品質與速度平衡 |
| Qwen2.5-7B Q4_K_M | 4.4 GB | 最高品質 |

模型下載後儲存於 `~/.airtype/models/`。程式會根據硬體自動推薦最佳模型組合。

---

## FAQ（常見問題）

### 打包與建置

**Q：打包後模型管理頁面沒有任何模型可下載？**

確認 `models/manifest.json` 存在於專案根目錄。此檔案會在打包時自動包含至執行檔目錄中。若手動執行 `pyinstaller`，請確保使用 `airtype.spec` 而非自行指定參數。

**Q：打包後的程式啟動很慢？**

請確認使用的是 `airtype.spec` 中的 **onedir**（目錄模式）打包。onefile（單檔模式）每次啟動都需要解壓所有依賴到臨時目錄，包含 PySide6、onnxruntime 等大型二進位檔時，解壓可能耗時數十秒。onedir 模式不需解壓，啟動速度接近原始碼執行。

**Q：可以用 `--onefile` 嗎？**

技術上可以，但不建議。Airtype 包含大量二進位依賴（Qt、ONNX Runtime 等），onefile 模式會導致每次冷啟動額外延遲 10–30 秒。若需要單檔分發，建議透過 NSIS / DMG / AppImage 製作安裝程式。

**Q：`pyinstaller airtype.spec` 報錯找不到模組？**

確認已安裝打包依賴：`pip install -e ".[packaging]"`。若需要額外引擎（如 Breeze-ASR），可額外安裝對應 extras。

**Q：打包後體積多大？**

使用建置腳本（乾淨 venv + `[packaging]`）打包，約 250-350MB（不含模型）。若使用 `[full]` 安裝後打包，會因為 PyTorch、transformers 等巨型套件膨脹至 2GB+。建置腳本會自動建立乾淨 venv 避免此問題。

### 執行與設定

**Q：啟動時報 `No audio device found` 錯誤？**

這是非致命警告。Airtype 會在無麥克風的環境中降級執行，此時語音辨識功能不可用，但設定介面與其他功能仍正常。接上麥克風後重啟即可。

**Q：設定檔在哪裡？**

`~/.airtype/config.json`（Windows 為 `%USERPROFILE%\.airtype\config.json`）。首次執行自動建立預設設定。

**Q：模型下載到哪裡？如何刪除？**

所有模型儲存於 `~/.airtype/models/`。可以在「設定 → 模型管理」中刪除已下載的模型，或直接刪除對應的目錄/檔案。

**Q：如何設定 HuggingFace Token？**

部分模型可能需要 HuggingFace 帳號。Airtype 會自動偵測以下來源的 token（優先順序由高到低）：

1. 系統 keyring 中的 `huggingface` 項目
2. 環境變數 `HF_TOKEN` 或 `HUGGING_FACE_HUB_TOKEN`
3. `~/.cache/huggingface/token` 快取檔（由 `huggingface-cli login` 產生）

**Q：API 金鑰如何儲存？**

API 金鑰透過系統 keyring 安全儲存（Windows Credential Manager / macOS Keychain / Linux Secret Service），不會出現在 `config.json` 或 log 中。

### 平台特定

**Q：macOS 無法開啟 app，顯示「已損壞」或「無法驗證開發者」？**

未經簽署的 app 需要手動允許：

```bash
xattr -cr /Applications/Airtype.app
```

或在「系統偏好設定 → 安全性與隱私」中點擊「仍要開啟」。正式發行版會包含 Apple 簽署與公證。

**Q：Linux 上快捷鍵不起作用？**

pynput 在 Wayland 下可能無法捕獲全域快捷鍵。建議使用 X11 session，或安裝 `xdotool`：

```bash
sudo apt install xdotool
```

**Q：Windows Defender 誤報病毒？**

PyInstaller 打包的程式偶爾會被防毒軟體誤判。這是已知問題。可以在 Windows Defender 中將 `dist\airtype\` 目錄加入排除清單。正式發行版會加入程式碼簽章以避免此問題。
