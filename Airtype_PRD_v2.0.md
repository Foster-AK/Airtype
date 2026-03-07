# Airtype 空音輸入 — 產品需求文件（PRD）

> **版本**：v2.0  
> **日期**：2026 年 3 月 3 日  
> **作者**：Foster  
> **狀態**：Draft  
> **技術棧**：Python + PySide6 + Qwen3-ASR / Breeze-ASR-25  
> **目標平台**：Windows / macOS / Linux

---

## 目錄

1. [產品概述](#1-產品概述)
2. [目標使用者與使用場景](#2-目標使用者與使用場景)
3. [系統架構](#3-系統架構)
4. [功能規格：語音輸入介面（Voice Input Overlay）](#4-功能規格語音輸入介面voice-input-overlay)
5. [功能規格：設定介面（Settings Panel）](#5-功能規格設定介面settings-panel)
6. [核心引擎規格](#6-核心引擎規格)
7. [跨平台技術規格](#7-跨平台技術規格)
8. [資料流與狀態機](#8-資料流與狀態機)
9. [安全性與隱私](#9-安全性與隱私)
10. [效能指標](#10-效能指標)
11. [開發階段與里程碑](#11-開發階段與里程碑)
12. [風險評估與對策](#12-風險評估與對策)
13. [附錄](#13-附錄)

---

## 1. 產品概述

### 1.1 產品定義

Airtype（空音輸入）是一款跨平台的離線語音即時輸入工具，以台灣繁體中文為主要辨識語言。使用者在任何應用程式中按下快捷鍵，即可呼叫浮動語音輸入介面，透過說話直接將文字輸入到當前的文字編輯器或應用中。核心 ASR 引擎採用阿里巴巴通義團隊的 Qwen3-ASR（開源 SOTA 級語音辨識模型），同時支援聯發創新基地的 Breeze-ASR-25（台灣華語與中英混用最佳化）等備選模型。所有語音辨識均在本機執行，不需要網路連線，確保資料隱私與低延遲。

### 1.2 產品願景

> 讓語音成為鍵盤的自然延伸——不切換視窗、不離開當前工作流、不需要雲端，說完即輸入。

### 1.3 核心價值主張

| 價值 | 說明 |
|------|------|
| **零干擾** | 浮動膠囊介面不搶焦點、不遮擋工作區，用完即消失 |
| **完全離線** | ASR 引擎在本機運行，無需網路，語音資料不離開設備 |
| **跨平台一致** | Windows、macOS、Linux 上的體驗與功能完全一致 |
| **智慧潤飾** | 可選的 LLM 後處理，自動修正語句、補充標點、潤飾文法 |
| **可擴展** | 支援自訂辭典、多 ASR 模型切換、多語言辨識 |

### 1.4 與既有方案的差異

| 特性 | Airtype | Windows 語音輸入 | macOS 聽寫 | Google Docs 語音 |
|------|---------|-----------------|-----------|-----------------|
| 離線運作 | ✅ | 部分 | 部分 | ❌ |
| 跨平台 | ✅ | ❌ | ❌ | 僅瀏覽器 |
| 任意應用注入 | ✅ | ✅ | ✅ | ❌（僅 Docs） |
| 台灣繁中最佳化 | ✅（Breeze-ASR-25） | ❌ | 部分 | 部分 |
| 52 語言/方言 | ✅（Qwen3-ASR） | 有限 | 有限 | ✅ |
| 自訂辭典 | ✅ | ❌ | ❌ | ❌ |
| LLM 潤飾 | ✅ | ❌ | ❌ | ❌ |
| ASR 模型可選 | ✅ | ❌ | ❌ | ❌ |
| 不搶焦點 | ✅ | ❌（會開面板）| ❌ | N/A |

---

## 2. 目標使用者與使用場景

### 2.1 目標使用者畫像

**主要使用者：知識工作者**
- 每天大量文字輸入的軟體工程師、寫作者、研究人員
- 需要在 IDE、文件編輯器、通訊軟體間快速切換輸入
- 重視效率，不願為了語音輸入而中斷工作流

**次要使用者：多語言使用者**
- 需要中英文混合輸入的雙語工作者
- 輸入法切換頻繁，語音輸入可大幅降低摩擦

**潛在使用者：無障礙需求者**
- 因手部傷害或身體狀況需要減少鍵盤使用的使用者
- 需要長時間穩定的語音輸入方案

### 2.2 核心使用場景

**場景 A：編輯器中的快速語音輸入**
> Foster 正在 VS Code 中撰寫技術文件。他需要輸入一段中文說明，但手指正在操作滑鼠。他按下 `Ctrl+Shift+Space`，螢幕中央出現浮動膠囊，他對著麥克風說：「這個函數負責處理使用者的驗證邏輯，包含 token 的生成與驗證」。說完停頓一秒，文字自動出現在 VS Code 的游標位置，膠囊消失。全程不到 5 秒。

**場景 B：通訊軟體的訊息回覆**
> Foster 在 Slack 中收到同事的訊息，他按下快捷鍵，說：「好的，我下午三點可以開會，請幫我預約會議室」。LLM 潤飾自動將口語修正為：「好的，我下午三點可以開會。請協助預約會議室，謝謝。」文字直接出現在 Slack 的輸入框中。

**場景 C：專業術語密集的文件輸入**
> Foster 正在撰寫 ERP 系統文件，需要輸入大量鼎新 Workflow 的專有名詞。他在設定中載入了自訂的 ERP 術語辭典，辨識引擎能正確辨識「拋轉」「過帳」「沖銷」等專業術語，不再產生同音錯字。

**場景 D：切換 ASR 模型以適應不同場景**
> Foster 日常使用 Qwen3-ASR-0.6B 進行中文語音輸入，辨識速度極快。但他注意到某些台灣特有用語（如「拋轉」「沖銷」）偶爾會辨識錯誤。他在設定面板中將 ASR 模型切換到 Breeze-ASR-25（聯發創新基地專為台灣華語最佳化的模型），中英混用的辨識準確度立刻提升。需要處理多語言會議紀錄時，他再切回 Qwen3-ASR-1.7B，利用其 52 語言的廣泛支援來辨識。

---

## 3. 系統架構

### 3.1 高層架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                        Airtype Application                       │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Global       │  │  Settings    │  │  System Tray            │ │
│  │  Hotkey       │  │  Panel       │  │  (常駐圖示)              │ │
│  │  Listener     │  │  (設定面板)   │  │                         │ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────────────┘ │
│         │                  │                    │                  │
│  ┌──────▼──────────────────▼────────────────────▼────────────┐   │
│  │                    Core Controller                         │   │
│  │              (狀態管理 / 事件分發 / 設定管理)                │   │
│  └──┬──────────┬──────────┬──────────┬──────────┬───────────┘   │
│     │          │          │          │          │                │
│  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼───┐  ┌──▼──────────┐    │
│  │Audio │  │ VAD  │  │ ASR  │  │ LLM  │  │ Text        │    │
│  │Capture│  │Engine│  │Engine│  │Polish│  │ Injector    │    │
│  │音訊擷取│ │靜音偵測│ │語音辨識│ │潤飾引擎│ │文字注入      │    │
│  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬──────────┘    │
│     │          │          │          │          │                │
│  ┌──▼──────────▼──────────▼──────────▼──────────▼───────────┐   │
│  │                 Overlay UI (PySide6)                       │   │
│  │          浮動膠囊 + 音波圖 + 狀態顯示                       │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 模組職責

| 模組 | 職責 | 技術 |
|------|------|------|
| **Global Hotkey Listener** | 系統級快捷鍵監聽，觸發錄音開始/結束 | pynput |
| **Audio Capture** | 從指定麥克風擷取即時音訊串流 | sounddevice (PortAudio) |
| **VAD Engine** | 語音活動偵測，判斷「有人說話」或「靜默」 | Silero VAD (ONNX) |
| **ASR Engine** | 語音轉文字，支援多模型切換 | Qwen3-ASR (qwen-asr) / Breeze-ASR-25 / sherpa-onnx |
| **LLM Polish** | 文字後處理：標點修正、語句潤飾、格式調整 | 本機 LLM 或 API |
| **Text Injector** | 將辨識結果注入目標應用的游標位置 | pyperclip + pyautogui |
| **Overlay UI** | 浮動膠囊介面、音波圖動畫、狀態顯示 | PySide6 (Qt) |
| **Settings Panel** | 使用者設定介面：模型選擇、辭典管理、偏好設定 | PySide6 (Qt) |
| **System Tray** | 系統匣常駐圖示，提供快速存取與狀態顯示 | PySide6 QSystemTrayIcon |
| **Core Controller** | 中央狀態管理、事件分發、設定持久化 | Python dataclass + JSON |

### 3.3 執行緒架構

```
Main Thread (Qt Event Loop)
  ├── Overlay UI 渲染
  ├── Settings Panel
  └── System Tray

Worker Thread: Audio Pipeline
  ├── sounddevice callback → 音訊 buffer
  ├── VAD 判斷 → 語音/靜默訊號
  └── 音量資料 → UI 音波圖（透過 Qt Signal）

Worker Thread: ASR Processing
  ├── 接收音訊 chunk
  ├── 執行辨識
  └── 回傳文字結果（透過 Qt Signal）

Worker Thread: LLM Polish（可選）
  ├── 接收 ASR 原始文字
  ├── 執行潤飾
  └── 回傳潤飾結果

Background Thread: Global Hotkey
  └── pynput listener（獨立事件迴圈）
```

---

## 4. 功能規格：語音輸入介面（Voice Input Overlay）

### 4.1 介面設計

參考設計如下：浮動膠囊懸停在使用者工作區上方，採深色半透明設計，包含動態音波圖與麥克風控制。

#### 4.1.1 浮動膠囊（Floating Pill）

| 屬性 | 規格 |
|------|------|
| 形狀 | 圓角膠囊形（border-radius = height / 2） |
| 尺寸 | 約 200 × 50 px（可依 DPI 縮放） |
| 背景 | 深色半透明（`rgba(10, 10, 20, 0.92)`）+ 背景模糊（20px） |
| 陰影 | 聆聽中：藍色光暈 `0 4px 24px rgba(59,130,246,0.25)`；閒置：暗色陰影 |
| 位置 | 預設螢幕中央偏下，可拖曳自訂位置（記憶上次位置） |
| 視窗屬性 | 無邊框、永遠置頂、不搶焦點（`Qt.Tool + WA_ShowWithoutActivating`） |
| 動畫 | 出現：從下方滑入 + 淡入（200ms）；消失：向下滑出 + 淡出（150ms） |

#### 4.1.2 膠囊內部佈局

```
┌──────────────────────────────────────────────┐
│  ┃┃ ┃ ┃┃┃┃ ┃    │    🎙️   ▾               │
│  音波圖 (7 bars)   │   麥克風  裝置選擇       │
└──────────────────────────────────────────────┘
                   LISTENING...
```

**左區 — 動態音波圖**

| 屬性 | 規格 |
|------|------|
| 柱狀數量 | 7 根 |
| 柱狀寬度 | 3.5px，間距 3px |
| 高度範圍 | 靜默 4px ↔ 最大 28px |
| 色彩 | 聆聽中：藍白漸層（`#60a5fa → #ffffff`）；閒置：半透明白 |
| 動畫 | 多層 sine wave 疊加 + 隨機擾動，中間柱較高 |
| 資料來源 | 即時音訊 RMS 音量值，透過 Qt Signal 從 Audio Thread 傳遞 |

**中區 — 分隔線**

- 垂直分隔線，1px 寬，`rgba(255,255,255,0.12)`

**右區 — 麥克風按鈕 + 裝置選擇**

| 元素 | 行為 |
|------|------|
| 麥克風圖示 | 點擊可開始/停止錄音（與快捷鍵等效） |
| 麥克風狀態 | 聆聽中：藍色高亮背景 + 藍色圖示；閒置：暗色 |
| ▾ 下拉箭頭 | 點擊展開音訊裝置選擇選單 |

**下方 — 狀態文字**

| 狀態 | 顯示文字 | 色彩 |
|------|---------|------|
| 待命 | `PRESS TO START` | 灰色（低對比） |
| 聆聽中 | `LISTENING...` | 藍色 `#60a5fa` |
| 處理中 | `PROCESSING...` | 白色 |
| 輸入中 | `INPUTTING...` | 綠色 |
| 錯誤 | `ERROR: {message}` | 紅色 |

#### 4.1.3 音訊裝置選擇下拉選單

按下膠囊右側 ▾ 按鈕時展開的浮動選單：

| 屬性 | 規格 |
|------|------|
| 背景 | 深色半透明（`rgba(15, 15, 25, 0.95)`）+ 背景模糊 |
| 圓角 | 12px |
| 寬度 | 260px |
| 標題 | 「音訊輸入裝置」灰色小字 |
| 項目 | 裝置名稱 + 裝置圖示 + 選中勾選標記 |
| 資料來源 | `sounddevice.query_devices(kind='input')` 動態取得 |
| 選中指示 | 藍色背景高亮 + ✓ 勾選圖示 |
| 出現動畫 | 從上方滑入 + 淡入（150ms） |

### 4.2 互動流程

```
使用者在任意應用中工作（如 VS Code）
  │
  ├── 按下快捷鍵 Ctrl+Shift+Space
  │       │
  │       ├── 系統記住當前焦點視窗
  │       ├── 膠囊從下方滑入出現（不搶焦點）
  │       ├── 自動開始音訊擷取
  │       ├── 狀態顯示 "LISTENING..."
  │       │
  │       ├── 使用者說話
  │       │     ├── 音波圖即時動態回饋
  │       │     ├── VAD 偵測到語音 → 開始累積音訊
  │       │     └── ASR 串流辨識（可選：即時預覽文字）
  │       │
  │       ├── 觸發結束條件（以下任一）：
  │       │     ├── A. 靜音超過設定秒數（預設 1.5 秒）
  │       │     ├── B. 使用者再次按下快捷鍵
  │       │     └── C. 使用者點擊膠囊麥克風按鈕
  │       │
  │       ├── 狀態切換 "PROCESSING..."
  │       ├── ASR 最終辨識 → 取得原始文字
  │       │
  │       ├── [可選] LLM 潤飾
  │       │     ├── 標點符號修正
  │       │     ├── 語句潤飾
  │       │     └── 辭典詞彙替換
  │       │
  │       ├── 狀態切換 "INPUTTING..."
  │       ├── 文字注入到原焦點視窗
  │       │     ├── 備份剪貼簿
  │       │     ├── 寫入辨識結果到剪貼簿
  │       │     ├── 還原焦點到原視窗
  │       │     ├── 模擬 Ctrl+V 貼上
  │       │     └── 還原原始剪貼簿內容
  │       │
  │       └── 膠囊向下滑出消失
  │
  └── 文字出現在原應用游標位置 ✅
```

### 4.3 快捷鍵規格

| 快捷鍵 | 功能 | 可自訂 |
|--------|------|--------|
| `Ctrl+Shift+Space` | 開始/結束語音輸入（Toggle） | ✅ |
| `Escape` | 取消當前錄音（不注入文字） | ❌ |
| `Ctrl+Shift+S` | 開啟設定面板 | ✅ |

快捷鍵衝突處理：如果偵測到與其他應用衝突，首次啟動時提示使用者更換組合鍵。

---

## 5. 功能規格：設定介面（Settings Panel）

### 5.1 設定面板總覽

設定面板是獨立視窗，透過系統匣圖示或快捷鍵 `Ctrl+Shift+S` 開啟。採分頁式設計，左側為導航欄，右側為設定內容。

#### 5.1.1 視窗規格

| 屬性 | 規格 |
|------|------|
| 尺寸 | 720 × 520 px（可調整大小，最小 600 × 450） |
| 風格 | 與系統主題一致（支援 Light / Dark mode） |
| 關閉行為 | 關閉設定面板不會退出應用（僅隱藏視窗） |
| 儲存 | 所有變更即時自動儲存至 `~/.airtype/config.json` |

#### 5.1.2 分頁結構

```
┌──────────────────────────────────────────────────────────┐
│  Airtype 設定                                      ─ □ ✕ │
├────────────┬─────────────────────────────────────────────┤
│            │                                             │
│  ⚡ 一般    │  （各分頁內容）                               │
│  🎤 語音    │                                             │
│  🤖 AI 潤飾 │                                             │
│  📖 辭典    │                                             │
│  🎨 外觀    │                                             │
│  ⌨️ 快捷鍵  │                                             │
│  ℹ️ 關於    │                                             │
│            │                                             │
├────────────┴─────────────────────────────────────────────┤
│  Airtype v2.0  ·  設定自動儲存                             │
└──────────────────────────────────────────────────────────┘
```

### 5.2 分頁一：一般設定（General）

| 設定項 | 類型 | 預設值 | 說明 |
|--------|------|--------|------|
| 開機自動啟動 | Toggle | OFF | 系統啟動時自動執行 Airtype |
| 啟動時最小化 | Toggle | ON | 啟動後只在系統匣顯示 |
| 語言 | Dropdown | 繁體中文 | 介面語言（繁中/簡中/English/日本語） |
| 靜音自動結束秒數 | Slider | 1.5s | VAD 偵測靜音後自動結束的等待時間（0.5s ~ 5.0s） |
| 輸入後自動加空格 | Toggle | OFF | 英文模式下自動在結尾加空格 |
| 輸入後自動加換行 | Toggle | OFF | 每次語音輸入後自動加換行符 |
| 系統通知 | Toggle | ON | 辨識完成後顯示系統通知 |
| 日誌等級 | Dropdown | INFO | 除錯用日誌等級（DEBUG / INFO / WARN / ERROR） |

### 5.3 分頁二：語音設定（Voice / ASR）

#### 5.3.1 音訊輸入裝置

| 設定項 | 類型 | 說明 |
|--------|------|------|
| 輸入裝置 | Dropdown | 從系統可用麥克風列表中選擇（動態偵測） |
| 🔄 重新偵測 | Button | 重新掃描可用音訊裝置 |
| 輸入音量 | Slider + Meter | 調整增益 + 即時音量條顯示 |
| 降噪 | Toggle | 啟用軟體降噪前處理（RNNoise） |
| 試聽 | Button | 錄製 3 秒 → 播放 → 確認裝置正常 |

#### 5.3.2 ASR 語音辨識模型

| 設定項 | 類型 | 說明 |
|--------|------|------|
| 辨識模型 | Dropdown | 可用模型列表（見下方表格） |
| 辨識語言 | Dropdown | 模型支援的語言列表，或「自動偵測」 |
| 模型下載管理 | Section | 顯示已下載/可下載的模型，附大小與下載進度 |

**預設可選 ASR 模型**

| 模型 | 來源 | 大小 | 語言支援 | 特性 | 推薦場景 |
|------|------|------|---------|------|---------|
| ⭐ **Qwen3-ASR-0.6B** | 阿里通義 | ~1.2GB | 52 語言/方言（含 22 種中文方言） | 速度極快，精準度效率最佳平衡，串流/離線統一推理 | **日常首選（預設）**，一般中文輸入 |
| **Qwen3-ASR-1.7B** | 阿里通義 | ~3.4GB | 52 語言/方言（含 22 種中文方言） | 開源 SOTA，抗噪能力極強，支援歌詞/音樂辨識 | 會議紀錄、多語言、高精度需求 |
| **Breeze-ASR-25** | 聯發創新基地 (MediaTek Research) | ~1.5GB | 台灣華語 + 英語 | 基於 Whisper-large-v2 微調，比 Whisper 提升 10%，中英混用提升 56% | **台灣用語最佳化**，中英 code-switching |
| **SenseVoice-Small** | 阿里 FunASR | ~200MB | 中/英/日/韓/粵 | 超輕量，sherpa-onnx 原生支援 | 低資源設備、嵌入式 |
| **Whisper-Medium** | OpenAI | ~1.5GB | 99 種語言 | 多語言廣泛 | 少見語言辨識 |
| **Whisper-Large-v3** | OpenAI | ~3.1GB | 99 種語言 | 品質最高的 Whisper 版本 | Whisper 生態整合 |
| **Paraformer-zh** | 阿里 FunASR | ~220MB | 中/英 | 中文極佳，sherpa-onnx 原生支援 | 中文專業場景（輕量備選） |
| **自訂模型** | — | — | — | 使用者自行匯入模型 | 特定領域 |

**模型選擇指引**

| 需求場景 | 推薦模型 | 理由 |
|---------|---------|------|
| 日常繁中輸入（速度優先） | Qwen3-ASR-0.6B | 速度極快，52 語言自動偵測，0.6B 即達高精度 |
| 高精度多語言辨識 | Qwen3-ASR-1.7B | 開源 SOTA，與 GPT-4o-Transcribe 等商業 API 競爭 |
| 台灣口音 + 中英混用 | Breeze-ASR-25 | 專為台灣華語調校，中英 code-switching 表現最佳 |
| 低資源/嵌入式設備 | SenseVoice-Small | 僅 200MB，CPU 即可流暢運行 |

**重要技術備註**

> - **Qwen3-ASR** 使用 `qwen-asr` Python 套件或 vLLM 後端進行推理，支援串流與離線統一推理，需 GPU（建議 NVIDIA）以獲得最佳效能，CPU 推理亦可但速度較慢。模型內建語言自動偵測，支援中國各方言（含閩南語、粵語、吳語等 22 種方言）。
> - **Breeze-ASR-25** 基於 Whisper-large-v2 架構，可透過 HuggingFace Transformers pipeline 或 faster-whisper 進行推理，與 Whisper 生態完全相容。Apache 2.0 授權。
> - **SenseVoice / Paraformer** 透過 sherpa-onnx 原生支援，ONNX 格式，CPU 友好，延遲最低。
> - 所有模型均為開源授權，支援本機離線部署。

#### 5.3.3 辨識模式

| 設定項 | 類型 | 預設值 | 說明 |
|--------|------|--------|------|
| 辨識模式 | Radio | 批次 | **批次**：錄完後一次辨識（品質最佳，所有模型支援）；**串流**：邊說邊辨識（即時預覽，Qwen3-ASR + vLLM / sherpa-onnx 支援） |
| 串流預覽 | Toggle | ON | 串流模式下，在膠囊下方即時顯示辨識中的文字 |

> **備註**：Breeze-ASR-25 為 Whisper 架構，原生不支援串流辨識。串流模式下系統會透過 VAD 分段 + 逐段辨識來模擬即時效果。建議需要串流辨識時切換至 Qwen3-ASR。

### 5.4 分頁三：AI 潤飾設定（LLM Polish）

#### 5.4.1 總開關與模式

| 設定項 | 類型 | 預設值 | 說明 |
|--------|------|--------|------|
| 啟用 AI 潤飾 | Toggle | OFF | 總開關，關閉時直接輸出 ASR 原始結果 |
| 潤飾模式 | Radio | 輕度 | **輕度**：僅標點修正；**中度**：標點 + 語句通順；**完整**：標點 + 語句 + 文法潤飾 |
| 潤飾前預覽 | Toggle | ON | 輸入前先顯示原始/潤飾對照，使用者可選擇使用哪個版本 |

#### 5.4.2 LLM 模型選擇

| 設定項 | 類型 | 說明 |
|--------|------|------|
| 模型來源 | Radio | **本機模型** / **API 服務** |
| 本機模型 | Dropdown | 可選本機 LLM 列表（見下方） |
| API 服務 | Dropdown | 可選 API 供應商列表（見下方） |
| API Key | Password Input | API 金鑰設定（加密儲存） |
| API Endpoint | Text Input | 自訂 API 端點（支援 OpenAI 相容 API） |
| 自訂 Prompt | Text Area | 自訂潤飾指令模板 |

**本機 LLM 模型選項**

| 模型 | 大小 | 速度 | 說明 |
|------|------|------|------|
| **Qwen2.5-1.5B** | ~1.2GB | 極快 | 輕量級，適合標點修正 |
| **Qwen2.5-7B** | ~4.5GB | 快 | 均衡型，適合中度潤飾 |
| **Llama-3.2-3B** | ~2.0GB | 極快 | 英文為主的潤飾 |
| **自訂模型** | — | — | 使用者匯入 GGUF 格式模型 |

**API 服務選項**

| 服務 | 支援模型 | 說明 |
|------|---------|------|
| **Anthropic Claude** | Claude Sonnet / Haiku | 需要 API Key |
| **OpenAI** | GPT-4o-mini / GPT-4o | 需要 API Key |
| **Ollama（本機）** | 所有 Ollama 已安裝模型 | 需要本機運行 Ollama |
| **自訂 OpenAI 相容** | — | 輸入自訂 endpoint + key |

#### 5.4.3 潤飾規則細項

| 設定項 | 類型 | 預設值 | 說明 |
|--------|------|--------|------|
| 自動加標點 | Toggle | ON | 自動在適當位置插入逗號、句號等 |
| 修正同音字 | Toggle | ON | 利用上下文修正 ASR 同音錯字 |
| 口語轉書面 | Toggle | OFF | 「然後就是那個」→「接著」 |
| 保留語氣詞 | Toggle | ON | 保留「嗯」「啊」等語氣詞（OFF 則移除） |
| 繁簡轉換 | Dropdown | 不轉換 | 不轉換 / 簡→繁 / 繁→簡 |
| 數字格式 | Dropdown | 智慧判斷 | 阿拉伯數字 / 中文數字 / 智慧判斷 |

### 5.5 分頁四：辭典管理（Dictionary）

#### 5.5.1 辭典功能概述

自訂辭典讓 ASR 引擎優先辨識專業術語、人名、公司名稱等。辭典分為「熱詞表」和「替換規則」兩種機制。

#### 5.5.2 熱詞表（Hot Words）

提高特定詞彙的辨識優先權，不改變辨識結果文字。

| 設定項 | 類型 | 說明 |
|--------|------|------|
| 熱詞列表 | Editable Table | 詞彙 + 權重（1~10） |
| 匯入 | Button | 從 .txt / .csv 匯入 |
| 匯出 | Button | 匯出為 .txt / .csv |
| 啟用 / 停用 | Toggle per entry | 個別詞彙可快速啟停 |

**熱詞範例**

| 詞彙 | 權重 | 類別 |
|------|------|------|
| 鼎新 Workflow | 8 | ERP 術語 |
| 拋轉 | 7 | ERP 術語 |
| PostgreSQL | 9 | 技術名詞 |
| sherpa-onnx | 9 | 技術名詞 |
| 過帳 | 7 | 會計術語 |
| 沖銷 | 7 | 會計術語 |

#### 5.5.3 替換規則（Replace Rules）

ASR 辨識完成後，自動執行文字替換。

| 設定項 | 類型 | 說明 |
|--------|------|------|
| 替換規則列表 | Editable Table | 原始文字 → 替換文字 |
| 支援正則表達式 | Toggle | 啟用 regex 替換 |
| 匯入 / 匯出 | Button | .json 格式 |

**替換規則範例**

| 原始（ASR 可能辨識出） | 替換為 | 類型 |
|----------------------|--------|------|
| 頂新 | 鼎新 | 同音修正 |
| 拋磚 | 拋轉 | 專業術語 |
| post SQL | PostgreSQL | 技術名詞 |
| `(?<!\d)\.(\d)` | `。$1` | 正則：句號修正 |

#### 5.5.4 辭典集（Dictionary Sets）

使用者可建立多個辭典集，依場景快速切換。

| 操作 | 說明 |
|------|------|
| 新增辭典集 | 建立空白辭典集，命名如「ERP 術語」「會議常用」 |
| 啟用辭典集 | 可同時啟用多個辭典集（取聯集） |
| 快速切換 | 在系統匣右鍵選單中快速切換辭典集 |
| 分享 | 匯出為 `.airtype-dict` 檔案，分享給同事 |

### 5.6 分頁五：外觀設定（Appearance）

| 設定項 | 類型 | 預設值 | 說明 |
|--------|------|--------|------|
| 主題 | Radio | 跟隨系統 | 淺色 / 深色 / 跟隨系統 |
| 膠囊位置 | Dropdown | 螢幕中央 | 螢幕中央 / 游標附近 / 自訂固定位置 |
| 膠囊大小 | Slider | 100% | 80% ~ 150% 縮放 |
| 膠囊透明度 | Slider | 92% | 50% ~ 100% |
| 音波圖風格 | Dropdown | 柱狀 | 柱狀（Bars）/ 波形（Waveform）/ 圓形（Circle） |
| 音波圖色彩 | Color Picker | 藍白漸層 | 自訂音波圖色彩 |
| 顯示狀態文字 | Toggle | ON | 膠囊下方是否顯示狀態文字 |
| 顯示即時文字預覽 | Toggle | ON | 辨識中是否在膠囊下方顯示即時文字 |

### 5.7 分頁六：快捷鍵設定（Shortcuts）

| 功能 | 預設快捷鍵 | 可自訂 |
|------|-----------|--------|
| 開始/結束語音輸入 | `Ctrl+Shift+Space` | ✅ |
| 取消錄音 | `Escape` | ✅ |
| 開啟設定面板 | `Ctrl+Shift+S` | ✅ |
| 切換辨識語言 | `Ctrl+Shift+L` | ✅ |
| 切換辭典集 | `Ctrl+Shift+D` | ✅ |
| 切換 LLM 潤飾 | `Ctrl+Shift+P` | ✅ |

快捷鍵設定介面支援「按下新組合鍵」直接錄入，並會即時偵測衝突。

### 5.8 分頁七：關於（About）

| 項目 | 內容 |
|------|------|
| 版本資訊 | 版號、建置日期、Python 版本 |
| 系統資訊 | OS、CPU、RAM、GPU（用於 ASR 加速判斷） |
| 模型資訊 | 當前已安裝的 ASR / LLM 模型列表與版本 |
| 授權條款 | 開源授權資訊 |
| 檢查更新 | 手動檢查新版本 |
| 回報問題 | 連結到 GitHub Issues |
| 匯出診斷資訊 | 打包系統 / 設定 / 日誌資訊，方便提交 Bug 報告 |

---

## 6. 核心引擎規格

### 6.1 音訊擷取引擎（Audio Capture）

| 參數 | 規格 |
|------|------|
| 取樣率 | 16000 Hz（ASR 引擎標準） |
| 位元深度 | 16-bit PCM / float32 |
| 聲道 | 單聲道（Mono） |
| 緩衝大小 | 512 samples（32ms @ 16kHz） |
| 框架 | sounddevice（基於 PortAudio） |
| 裝置切換 | 支援即時切換，不需重啟應用 |

### 6.2 語音活動偵測（VAD）

| 參數 | 規格 |
|------|------|
| 模型 | Silero VAD v5（ONNX Runtime） |
| 幀長度 | 512 samples（32ms） |
| 語音閾值 | 0.5（可在進階設定中調整） |
| 靜音結束閾值 | 連續靜音 1.5 秒（使用者可設定 0.5s ~ 5.0s） |
| 延遲 | < 30ms per frame |
| 記憶體佔用 | ~2MB |

**VAD 狀態機：**

```
    speech_prob >= 0.5         speech_prob < 0.5
IDLE ──────────────→ SPEECH ──────────────→ SILENCE_COUNTING
                       ↑                         │
                       │    speech_prob >= 0.5    │  靜音持續 >= threshold
                       └─────────────────────────┘        │
                                                          ▼
                                                    SPEECH_ENDED
                                                    → 觸發 ASR
```

### 6.3 ASR 語音辨識引擎

#### 6.3.1 引擎抽象層

所有 ASR 模型透過統一介面操作，隱藏底層推理框架差異：

```python
class ASREngine(Protocol):
    def load_model(self, model_path: str, config: dict) -> None: ...
    def recognize(self, audio: np.ndarray) -> ASRResult: ...
    def recognize_stream(self, chunk: np.ndarray) -> PartialResult: ...
    def set_hot_words(self, words: list[HotWord]) -> None: ...
    def set_context(self, context_text: str) -> None: ...  # Qwen3-ASR 上下文偏置
    def get_supported_languages(self) -> list[str]: ...
    def unload(self) -> None: ...
```

#### 6.3.2 Qwen3-ASR 整合（首選引擎）

| 功能 | 說明 |
|------|------|
| 模型規格 | Qwen3-ASR-0.6B（快速）/ Qwen3-ASR-1.7B（高精度） |
| 推理框架 | 支援三種推理路徑（見下方） |
| 串流辨識 | ✅ 原生支援串流推理（vLLM 後端） |
| 離線辨識 | ✅ 批次推理，支援長音訊 |
| 語言偵測 | 自動偵測 52 種語言/方言，無需手動指定 |
| 上下文偏置 | 支援 system prompt 中注入背景文字（熱詞/文件/關鍵字），引導辨識結果 |
| 中文方言 | 支援閩南語、粵語、吳語、四川話等 22 種中文方言 |
| 授權 | Apache 2.0 |

**Qwen3-ASR 三種推理路徑**

參考 [QwenASRMiniTool](https://github.com/dseditor/QwenASRMiniTool) 的實作經驗，Qwen3-ASR 可透過三種推理路徑部署，依使用者硬體自動選擇最適方案：

| 推理路徑 | 硬體需求 | 精度 | 速度 | 模型檔案 | 說明 |
|---------|---------|------|------|---------|------|
| **OpenVINO INT8**（CPU 首選） | Intel 11th Gen+ 或同等 AMD CPU | 良好 | 快 | 0.6B ~1.2GB / 1.7B ~4.3GB（INT8 KV-Cache） | 純 CPU 即可執行，無需 GPU，適合廣泛部署 |
| **PyTorch CUDA**（GPU 首選） | NVIDIA GPU（RTX 系列） | 最高 | 最快 | 0.6B ~1.2GB / 1.7B ~3.4GB | bfloat16 推理，精度最高 |
| **chatllm.cpp + Vulkan**（跨 GPU） | 任何支援 Vulkan 的 GPU | 高 | 快 | GGUF 量化格式 | 支援 NVIDIA / AMD / Intel GPU，不限 CUDA |

> **實作參考**：QwenASRMiniTool 已驗證 OpenVINO INT8 路徑在 Windows 上的可行性——Qwen3-ASR-0.6B INT8 量化模型峰值 RAM 約 4.8GB，純 CPU 即可執行，無需任何 GPU。這對於 Airtype 的跨平台「開箱即用」體驗至關重要。

**OpenVINO INT8 推理實作要點**

基於 QwenASRMiniTool 的架構經驗，OpenVINO INT8 推理需要以下組件：

- `processor_numpy.py`：純 NumPy 實作的 Mel 頻譜 + BPE 分詞器，**完全不依賴 PyTorch**，大幅縮小部署體積
- `prompt_template.json`：從原始模型預先提取的 BPE prompt token ID 模板（一次性生成，隨程式分發）
- `mel_filters.npy`：預計算的 Mel 濾波器矩陣，避免執行時重算
- Silero VAD v4.0 (ONNX)：搭配使用的靜音偵測模型，與我們現有 VAD 方案一致
- 量化模型來源：`dseditor/Qwen3-ASR-0.6B-INT8_ASYM-OpenVINO`（HuggingFace）

**Qwen3-ASR 上下文偏置（Context Biasing）特色**

Qwen3-ASR 支援在辨識時注入背景文字作為上下文，可大幅提升專業術語的辨識準確度。支援格式包含：
- 簡單的關鍵字/熱詞列表
- 完整文件段落
- 關鍵字與全文混合格式
- 無需預處理，模型自動識別關鍵詞

此功能可與本應用的「辭典管理」模組整合，將使用者的熱詞表自動組裝為上下文注入 ASR。

#### 6.3.3 Breeze-ASR-25 整合（台灣華語最佳化引擎）

| 功能 | 說明 |
|------|------|
| 模型規格 | 基於 Whisper-large-v2 微調，~1.5GB |
| 推理框架 | HuggingFace Transformers pipeline / faster-whisper |
| 串流辨識 | ⚠️ 需透過 VAD 分段模擬串流 |
| 離線辨識 | ✅ |
| 台灣華語最佳化 | 比原版 Whisper 提升近 10% 辨識精準度 |
| 中英混用 (Code-switching) | 比原版 Whisper 提升 56%，支援句內/句間切換 |
| 時間對齊 | 增強的時間戳對齊，適合字幕生成 |
| GPU 加速 | CUDA（透過 CTranslate2） |
| 授權 | Apache 2.0（聯發創新基地 MediaTek Research） |

**Breeze-ASR-25 的台灣在地化優勢**

聯發創新基地透過強化台灣語料及台灣口音訓練，解決了一般語音辨識模型常見的在地用語辨識問題，例如不會再把「發生什麼事」辨識成「花生什麼事」。訓練資料包含來自 FineWeb2 的合成中文數據及 BreezyVoice TTS 生成的語料。

#### 6.3.4 sherpa-onnx 整合（輕量引擎）

| 功能 | 說明 |
|------|------|
| 支援模型 | SenseVoice、Paraformer、Zipformer、Whisper (ONNX) |
| 推理框架 | ONNX Runtime |
| 串流辨識 | ✅ OnlineRecognizer |
| 離線辨識 | ✅ OfflineRecognizer |
| 熱詞 | 透過 `hotwords_file` 參數載入 |
| GPU 加速 | CUDA / DirectML / CoreML |
| CPU 推理 | 極度最佳化，適合低資源設備 |
| 特色 | 啟動速度最快、記憶體佔用最低 |

#### 6.3.5 推理框架對照表

| 推理框架 | 對應模型 | 啟動速度 | GPU 需求 | 適用場景 |
|---------|---------|---------|---------|---------|
| **OpenVINO INT8** | Qwen3-ASR-0.6B / 1.7B INT8 量化 | 快 | ❌ 純 CPU | **跨平台首選**，開箱即用 |
| **PyTorch CUDA** | Qwen3-ASR-0.6B / 1.7B 原始權重 | 中等 | NVIDIA GPU | 最高精度，有 GPU 時首選 |
| **chatllm.cpp + Vulkan** | Qwen3-ASR GGUF 量化 | 快 | 任何 Vulkan GPU | AMD / Intel GPU 使用者 |
| **HF Transformers / faster-whisper** | Breeze-ASR-25, Whisper 系列 | 中等 | 建議有 GPU | 台灣華語、Whisper 系 |
| **sherpa-onnx (ONNX Runtime)** | SenseVoice, Paraformer, Zipformer | 極快 | ❌ 純 CPU | 快速啟動、低資源、嵌入式 |

#### 6.3.6 音訊前處理管線

參考 QwenASRMiniTool 的 `processor_numpy.py` 實作，音訊前處理可完全脫離 PyTorch 依賴：

```
原始音訊 (任意格式)
    │
    ├── sounddevice 擷取 (16kHz PCM Mono)
    │   或 ffmpeg 轉檔 (MP3/FLAC/M4A/OGG → WAV)
    │
    ├── 重取樣至 16kHz（若來源非 16kHz）
    │
    ├── Mel 頻譜提取（純 NumPy 實作）
    │   ├── mel_filters.npy（預計算 Mel 濾波器矩陣）
    │   ├── STFT → 幅度譜 → Mel 濾波 → Log-Mel
    │   └── 不依賴 torchaudio / librosa
    │
    ├── BPE 分詞（純 NumPy 實作）
    │   ├── prompt_template.json（預提取的 token ID 模板）
    │   └── 不依賴 transformers tokenizer
    │
    └── 送入 ASR 推理引擎
```

> **設計原則**：Airtype 的即時語音輸入場景，音訊來源固定為麥克風（16kHz PCM），不需要 ffmpeg 轉檔。但未來如需擴展為音檔轉字幕功能，可直接復用此前處理管線。

#### 6.3.7 模型下載與管理

| 功能 | 說明 |
|------|------|
| 自動下載 | 首次啟動或切換模型時，自動從 HuggingFace 下載 |
| 完整性檢查 | 下載完成後驗證檔案完整性（檔案大小 + hash），偵測 LFS 指標檔異常 |
| 備援下載源 | 主要下載源失敗時自動切換備援 URL |
| 下載進度 | UI 中顯示下載進度條與預估剩餘時間 |
| 按需下載 | 僅下載使用者選擇的模型，其餘模型標示「可下載」 |
| 模型目錄 | 預設 `~/.airtype/models/`，可在設定中自訂路徑 |
| 磁碟空間檢查 | 下載前檢查剩餘磁碟空間是否足夠 |

**預設模型下載源**

| 模型 | 主要來源 | 備援來源 |
|------|---------|---------|
| Qwen3-ASR-0.6B INT8 | `dseditor/Qwen3-ASR-0.6B-INT8_ASYM-OpenVINO` | `Echo9Zulu/Qwen3-ASR-0.6B-INT8_ASYM-OpenVINO` |
| Qwen3-ASR-1.7B INT8 | `dseditor/Qwen3-ASR-1.7B-INT8_OpenVINO` | — |
| Qwen3-ASR-0.6B 原始 | `Qwen/Qwen3-ASR-0.6B` | — |
| Qwen3-ASR-1.7B 原始 | `Qwen/Qwen3-ASR-1.7B` | — |
| Silero VAD v4.0 | `snakers4/silero-vad` | 內建於程式包 |
| Breeze-ASR-25 | `MediaTek-Research/Breeze-ASR-25` | — |

### 6.4 LLM 潤飾引擎

#### 6.4.1 處理管線

```
ASR 原始文字
    │
    ├──→ 辭典替換規則（正則/字串替換）
    │
    ├──→ LLM 潤飾（若啟用）
    │       ├── 輕度：僅標點
    │       ├── 中度：標點 + 通順
    │       └── 完整：標點 + 通順 + 文法
    │
    └──→ 最終輸出文字
```

#### 6.4.2 本機 LLM 執行

| 參數 | 規格 |
|------|------|
| 推理引擎 | llama.cpp（透過 llama-cpp-python） |
| 模型格式 | GGUF（量化格式） |
| 上下文長度 | 2048 tokens（語音輸入通常很短） |
| 生成長度 | 與輸入等長 ×1.5（上限） |
| 逾時 | 3 秒（超時則回傳原始文字） |

#### 6.4.3 潤飾 Prompt 模板

```
你是一個中文文字校對助手。請對以下語音辨識結果進行校正：
- 修正明顯的同音錯字
- 在適當位置添加標點符號
- 保持原意不變，不增刪內容
- 以繁體中文輸出
- 直接輸出修正後的文字，不要解釋

輸入：{asr_raw_text}
輸出：
```

使用者可在設定面板中自訂此 Prompt，例如加入特定領域的校正指引。

### 6.5 文字注入引擎

| 步驟 | 動作 | 耗時 |
|------|------|------|
| 1 | 備份剪貼簿內容 | ~5ms |
| 2 | 將辨識結果寫入剪貼簿 | ~5ms |
| 3 | 還原焦點到原應用視窗 | ~50ms |
| 4 | 模擬 Ctrl+V（macOS: Cmd+V）貼上 | ~20ms |
| 5 | 等待目標應用處理 | ~150ms |
| 6 | 還原原始剪貼簿內容 | ~5ms |
| **總計** | | **~235ms** |

**跨平台焦點管理：**

| 平台 | 焦點取得 | 焦點還原 |
|------|---------|---------|
| Windows | `ctypes.windll.user32.GetForegroundWindow()` | `SetForegroundWindow()` + `AttachThreadInput()` |
| macOS | `NSWorkspace.activeApplication()` 或 `osascript` | `NSRunningApplication.activate()` 或 `osascript` |
| Linux (X11) | `xdotool getactivewindow` | `xdotool windowactivate` |

---

## 7. 跨平台技術規格

### 7.1 技術棧總覽

| 層級 | 技術 | 說明 |
|------|------|------|
| 程式語言 | Python 3.11+ | 主要開發語言 |
| UI 框架 | PySide6 (Qt 6) | 跨平台 GUI，支援無邊框/透明/置頂 |
| 音訊 | sounddevice | 基於 PortAudio，跨平台音訊 I/O |
| ASR (首選) | Qwen3-ASR (qwen-asr) | 阿里通義開源 SOTA，52 語言，串流/離線統一 |
| ASR (台灣華語) | Breeze-ASR-25 (transformers/faster-whisper) | 聯發創新基地，台灣口音+中英混用最佳化 |
| ASR (輕量) | sherpa-onnx | ONNX Runtime，SenseVoice/Paraformer，CPU 友好 |
| VAD | Silero VAD (ONNX) | 輕量級語音活動偵測 |
| LLM (本機) | llama-cpp-python | llama.cpp 的 Python 綁定 |
| 快捷鍵 | pynput | 跨平台全域快捷鍵 |
| 剪貼簿 | pyperclip | 跨平台剪貼簿操作 |
| 模擬輸入 | pyautogui | 跨平台鍵盤/滑鼠模擬 |
| 設定儲存 | JSON | `~/.airtype/config.json` |
| 日誌 | Python logging | 結構化日誌輸出 |
| 打包 | PyInstaller / Nuitka | 單一執行檔打包 |

### 7.2 各平台特殊處理

| 功能 | Windows | macOS | Linux |
|------|---------|-------|-------|
| 全域快捷鍵 | pynput（正常） | pynput（需輔助使用權限） | pynput（X11 正常，Wayland 受限） |
| 不搶焦點視窗 | `Qt.Tool` flag | `Qt.Tool` flag | `Qt.Tool` flag |
| 焦點管理 | Win32 API | AppKit / osascript | xdotool |
| 系統匣 | QSystemTrayIcon | QSystemTrayIcon | QSystemTrayIcon（需 SNI） |
| 開機自啟 | Registry | LaunchAgent plist | XDG autostart |
| GPU 加速 | CUDA / DirectML / OpenVINO / Vulkan | CoreML（未來）/ OpenVINO | CUDA / Vulkan |
| 權限 | 無特殊需求 | 麥克風 + 輔助使用 | 可能需 input group |

### 7.3 專案目錄結構

```
airtype/
├── main.py                      # 應用入口
├── config.py                    # 設定模型與持久化
├── core/
│   ├── controller.py            # 核心控制器（狀態機、事件分發）
│   ├── hotkey.py                # 全域快捷鍵監聽
│   ├── audio_capture.py         # 音訊擷取 (sounddevice)
│   ├── vad.py                   # Silero VAD 封裝
│   ├── asr_engine.py            # ASR 引擎抽象層
│   ├── asr_qwen_openvino.py     # Qwen3-ASR OpenVINO INT8 實作（CPU 首選）
│   ├── asr_qwen_pytorch.py      # Qwen3-ASR PyTorch CUDA 實作（GPU 高精度）
│   ├── asr_qwen_vulkan.py       # Qwen3-ASR chatllm.cpp + Vulkan 實作（跨 GPU）
│   ├── asr_breeze.py            # Breeze-ASR-25 實作（transformers/faster-whisper）
│   ├── asr_sherpa.py            # sherpa-onnx 實作（SenseVoice/Paraformer）
│   ├── processor_numpy.py       # 純 NumPy Mel 頻譜 + BPE 處理器（不依賴 torch）
│   ├── llm_polish.py            # LLM 潤飾引擎
│   ├── dictionary.py            # 辭典管理（熱詞 + 替換規則）
│   └── text_injector.py         # 文字注入（剪貼簿方案）
├── ui/
│   ├── overlay.py               # 浮動膠囊主視窗
│   ├── waveform_widget.py       # 音波圖 QWidget
│   ├── device_selector.py       # 音訊裝置下拉選單
│   ├── settings_window.py       # 設定面板主視窗
│   ├── settings_general.py      # 一般設定分頁
│   ├── settings_voice.py        # 語音設定分頁
│   ├── settings_llm.py          # AI 潤飾設定分頁
│   ├── settings_dictionary.py   # 辭典管理分頁
│   ├── settings_appearance.py   # 外觀設定分頁
│   ├── settings_shortcuts.py    # 快捷鍵設定分頁
│   ├── settings_about.py        # 關於分頁
│   └── tray_icon.py             # 系統匣圖示
├── utils/
│   ├── platform_utils.py        # 跨平台工具（焦點管理、權限檢查）
│   ├── audio_utils.py           # 音訊格式轉換、重取樣
│   ├── model_manager.py         # 模型下載管理（完整性檢查、備援 URL、進度回報）
│   └── hardware_detect.py       # 硬體偵測（GPU/CPU 能力 → 自動推薦推理路徑）
├── models/                      # ASR / VAD / LLM 模型檔案
│   ├── vad/
│   │   └── silero_vad_v4.onnx
│   ├── asr/
│   │   ├── qwen3_asr_int8/      # OpenVINO INT8 量化（~1.2GB，自動下載）
│   │   ├── qwen3_asr_1p7b_kv_int8/  # 1.7B INT8 KV-Cache（~4.3GB，按需下載）
│   │   └── breeze_asr_25/       # Breeze-ASR-25（~1.5GB，按需下載）
│   ├── llm/
│   └── precomputed/
│       ├── mel_filters.npy      # 預計算 Mel 濾波器矩陣
│       └── prompt_template.json # BPE prompt token ID 模板
├── dictionaries/                # 使用者辭典檔案
│   └── default.json
├── resources/                   # 圖示、音效等靜態資源
│   ├── icons/
│   └── sounds/
├── tests/
│   ├── test_hotkey.py
│   ├── test_injector.py
│   ├── test_asr.py
│   └── test_vad.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

### 7.4 設定檔格式

設定檔位於 `~/.airtype/config.json`：

```json
{
  "version": "2.0",
  "general": {
    "language": "zh-TW",
    "auto_start": false,
    "start_minimized": true,
    "silence_timeout": 1.5,
    "append_space": false,
    "append_newline": false,
    "notifications": true,
    "log_level": "INFO"
  },
  "voice": {
    "input_device": "default",
    "noise_reduction": false,
    "asr_model": "qwen3-asr-0.6b",
    "asr_inference_backend": "auto",
    "asr_language": "zh-TW",
    "recognition_mode": "batch",
    "stream_preview": true
  },
  "llm": {
    "enabled": false,
    "mode": "light",
    "preview_before_inject": true,
    "source": "local",
    "local_model": "qwen2.5-1.5b",
    "api_provider": null,
    "api_key_encrypted": null,
    "api_endpoint": null,
    "custom_prompt": null,
    "auto_punctuation": true,
    "fix_homophones": true,
    "colloquial_to_formal": false,
    "keep_fillers": true,
    "cjk_conversion": "none",
    "number_format": "smart"
  },
  "dictionary": {
    "active_sets": ["default"],
    "hot_words": [
      { "word": "鼎新 Workflow", "weight": 8, "enabled": true },
      { "word": "PostgreSQL", "weight": 9, "enabled": true }
    ],
    "replace_rules": [
      { "from": "頂新", "to": "鼎新", "regex": false, "enabled": true }
    ]
  },
  "appearance": {
    "theme": "system",
    "pill_position": "center",
    "pill_scale": 1.0,
    "pill_opacity": 0.92,
    "waveform_style": "bars",
    "waveform_color": "#60a5fa",
    "show_status_text": true,
    "show_realtime_preview": true
  },
  "shortcuts": {
    "toggle_voice": "ctrl+shift+space",
    "cancel": "escape",
    "open_settings": "ctrl+shift+s",
    "switch_language": "ctrl+shift+l",
    "switch_dictionary": "ctrl+shift+d",
    "toggle_polish": "ctrl+shift+p"
  }
}
```

---

## 8. 資料流與狀態機

### 8.1 應用主狀態機

```
                    ┌──────────────────────────┐
                    │         IDLE             │
                    │   系統匣常駐，等待觸發     │
                    └─────────┬────────────────┘
                              │ 快捷鍵 / 麥克風按鈕
                    ┌─────────▼────────────────┐
                    │      ACTIVATING          │
                    │  記錄焦點視窗             │
                    │  初始化音訊擷取           │
                    │  顯示膠囊 (滑入動畫)      │
                    └─────────┬────────────────┘
                              │ 就緒
                    ┌─────────▼────────────────┐
              ┌────→│      LISTENING           │←────┐
              │     │  音訊擷取中               │     │
              │     │  VAD 即時偵測             │     │
              │     │  音波圖動態顯示           │     │
              │     └──┬──────────┬────────────┘     │
              │        │          │                   │
              │   VAD: 語音    VAD: 靜音              │
              │        │          │                   │
              │   ┌────▼───┐  ┌──▼─────────────┐    │
              │   │SPEAKING │  │SILENCE_COUNTING│    │
              │   │語音累積  │  │靜音計時中       │    │
              │   └────┬───┘  └──┬──────┬──────┘    │
              │        │         │      │            │
              │        └────┐    │   靜音 < threshold │
              │             │    │      └────────────┘
              │        VAD: │    │ 靜音 >= threshold
              │        靜音 │    │
              │             ▼    ▼
              │     ┌────────────────────────┐
              │     │    PROCESSING          │
     Escape / │     │  停止音訊擷取           │
     取消     │     │  ASR 辨識              │
              │     │  [LLM 潤飾]            │
              │     └─────────┬──────────────┘
              │               │ 辨識完成
              │     ┌─────────▼──────────────┐
              │     │    INJECTING           │
              │     │  還原焦點               │
              │     │  剪貼簿注入文字          │
              │     └─────────┬──────────────┘
              │               │ 注入完成
              │     ┌─────────▼──────────────┐
              └─────│     IDLE               │
                    │  膠囊消失 (滑出動畫)     │
                    └────────────────────────┘
```

### 8.2 音訊資料流

```
麥克風 (硬體)
    │
    │ PCM 16kHz Mono
    ▼
sounddevice callback (Audio Thread)
    │
    ├──→ Ring Buffer (3 秒循環緩衝)
    │       │
    │       ├──→ VAD Engine: 每 32ms 一幀判斷語音/靜默
    │       │       │
    │       │       └──→ Core Controller: 狀態轉移訊號
    │       │
    │       └──→ ASR Engine: 累積語音段落
    │               │
    │               ├──→ [串流模式] Partial Result → UI 即時預覽
    │               └──→ [批次模式] Final Result → LLM Polish → Text Injector
    │
    └──→ RMS Calculator: 每幀計算音量
            │
            └──→ Qt Signal → Overlay UI: 音波圖更新
```

---

## 9. 安全性與隱私

### 9.1 隱私保護原則

| 原則 | 實作方式 |
|------|---------|
| **語音不離開設備** | ASR 在本機離線執行，音訊資料不傳送到任何伺服器 |
| **音訊不持久化** | 錄音資料僅在記憶體中處理，辨識完成後立即釋放 |
| **API 呼叫最小化** | 僅在使用者明確啟用 LLM API 潤飾時才會傳送文字（非音訊） |
| **敏感設定加密** | API Key 使用系統 Keyring 加密儲存 |

### 9.2 資料處理流程

```
語音 (麥克風) → [本機] VAD → [本機] ASR → 文字
                                            │
                                ┌───────────┴───────────┐
                                │                       │
                          LLM 本機模式             LLM API 模式
                          (完全離線)              (文字送到 API)
                                │                       │
                                └───────────┬───────────┘
                                            │
                                      潤飾後文字
                                            │
                                      注入到目標應用
                                            │
                                      記憶體清除 ✅
```

### 9.3 安全措施

| 項目 | 措施 |
|------|------|
| API Key 儲存 | 使用系統 Keyring（Windows: Credential Manager, macOS: Keychain, Linux: Secret Service） |
| 設定檔權限 | `~/.airtype/` 目錄權限設為 `700`（僅使用者可讀寫） |
| 更新機制 | HTTPS 下載 + SHA256 校驗 |
| 錯誤日誌 | 日誌中不記錄辨識文字內容，僅記錄結構化事件 |

---

## 10. 效能指標

### 10.1 目標效能

| 指標 | 目標值 | 測量方式 |
|------|--------|---------|
| 啟動到可用 | < 3 秒 | 從雙擊圖示到系統匣圖示出現 |
| 快捷鍵回應 | < 100ms | 從按下快捷鍵到膠囊出現 |
| 音波圖幀率 | ≥ 30 FPS | 音波動畫流暢度 |
| VAD 延遲 | < 50ms | 從說話到 VAD 偵測到語音 |
| ASR 辨識延遲（批次） | < 2 秒 | 從結束錄音到文字產出（10 秒音訊，Qwen3-ASR-0.6B + GPU） |
| ASR 辨識延遲（串流） | < 500ms | 從說話到中間結果出現（Qwen3-ASR + vLLM 串流） |
| ASR 辨識延遲（CPU 輕量） | < 3 秒 | SenseVoice/Paraformer via sherpa-onnx，純 CPU |
| LLM 潤飾延遲 | < 3 秒 | 本機 7B 模型 |
| 文字注入延遲 | < 250ms | 從辨識完成到文字出現在目標應用 |
| 端到端延遲（無 LLM） | < 3 秒 | 從停止說話到文字注入完成 |
| 端到端延遲（含 LLM） | < 6 秒 | 包含本機 LLM 潤飾 |

### 10.2 資源佔用

| 資源 | 閒置 | 錄音中 | ASR 辨識中 |
|------|------|--------|-----------|
| CPU | < 1% | 5~10% | 30~80%（Qwen3-ASR OpenVINO INT8）/ 10~20%（sherpa-onnx） |
| RAM | < 150MB | < 200MB | **峰值 ~4.8GB**（Qwen3-ASR-0.6B INT8）/ 300~500MB（sherpa-onnx） |
| GPU VRAM（可選） | 0 | 0 | 1.5~4GB（Qwen3-ASR PyTorch CUDA 0.6B~1.7B） |
| 磁碟 | 模型檔案 200MB ~ 5GB | — | — |

> **實測數據參考**：根據 QwenASRMiniTool 的實測結果，Qwen3-ASR-0.6B OpenVINO INT8 在 Windows 上峰值 RAM 約 4.8GB，推薦系統 RAM ≥ 6GB。

### 10.3 最低系統需求

基於 QwenASRMiniTool 的實測驗證結果：

| 項目 | 最低需求（OpenVINO INT8） | 建議配備（GPU 模式） |
|------|------------------------|-------------------|
| OS | Windows 10/11 64-bit, macOS 11+, Ubuntu 22.04+ | 同左 |
| CPU | Intel 11th Gen+ 或同等 AMD | Intel 12th Gen+ / AMD Ryzen 5000+ |
| RAM | 6GB（0.6B 模型峰值 ~4.8GB） | 16GB（同時使用 LLM 潤飾） |
| GPU | 不需要 | NVIDIA RTX 系列（CUDA）或任何 Vulkan GPU |
| 磁碟 | 2GB（程式 + 0.6B 模型） | 10GB（多模型共存） |
| Python | 3.10+ | 3.11+ |

### 10.4 硬體自動偵測與推理路徑選擇

首次啟動時，Airtype 自動偵測使用者硬體並推薦最適推理路徑：

```
首次啟動 → 硬體偵測
    │
    ├── 偵測 NVIDIA GPU（CUDA）
    │     ├── VRAM ≥ 4GB → 推薦 PyTorch CUDA + Qwen3-ASR-1.7B
    │     └── VRAM ≥ 2GB → 推薦 PyTorch CUDA + Qwen3-ASR-0.6B
    │
    ├── 偵測 AMD / Intel GPU（Vulkan）
    │     └── 推薦 chatllm.cpp + Vulkan + Qwen3-ASR-0.6B
    │
    ├── 僅 CPU
    │     ├── RAM ≥ 6GB → 推薦 OpenVINO INT8 + Qwen3-ASR-0.6B
    │     └── RAM < 6GB → 推薦 sherpa-onnx + SenseVoice-Small（~200MB）
    │
    └── 使用者可隨時在設定中覆寫自動選擇
```

---

## 11. 開發階段與里程碑

### Phase 1：核心驗證（2 週）

> 目標：驗證跨平台基礎設施可行性

- [x] 全域快捷鍵（pynput 三平台驗證）
- [x] 文字注入（剪貼簿方案，中文/英文/Emoji）
- [x] 焦點視窗管理（記錄與還原）
- [ ] 音訊擷取（sounddevice 裝置列舉與擷取）
- [ ] VAD 整合（Silero VAD 基礎偵測）

### Phase 2：語音辨識管線（2 週）

> 目標：完成 ASR 辨識核心流程

- [ ] Qwen3-ASR OpenVINO INT8 整合（CPU 首選路徑，參考 QwenASRMiniTool 實作）
- [ ] 純 NumPy 音訊前處理器（processor_numpy.py，脫離 torch 依賴）
- [ ] Qwen3-ASR PyTorch CUDA 整合（GPU 高精度路徑）
- [ ] Qwen3-ASR 上下文偏置與辭典整合
- [ ] Breeze-ASR-25 整合（HuggingFace pipeline / faster-whisper）
- [ ] sherpa-onnx 整合（SenseVoice 輕量備選）
- [ ] 批次辨識流程（錄完 → 辨識 → 輸出）
- [ ] 串流辨識流程（Qwen3-ASR vLLM 串流 / VAD 分段模擬串流）
- [ ] ASR 引擎抽象層 + 多模型切換機制
- [ ] 硬體自動偵測 + 推理路徑自動選擇
- [ ] 模型下載管理器（完整性檢查、備援 URL、進度回報）
- [ ] 熱詞表支援（sherpa-onnx 原生 + Qwen3-ASR 上下文偏置）

### Phase 3：使用者介面（2 週）

> 目標：完成浮動膠囊 + 設定面板

- [ ] PySide6 浮動膠囊（無邊框/透明/不搶焦點）
- [ ] 動態音波圖 Widget
- [ ] 音訊裝置選擇下拉選單
- [ ] 系統匣圖示
- [ ] 設定面板框架（分頁式）
- [ ] 一般 / 語音 / 外觀設定頁

### Phase 4：智慧功能（2 週）

> 目標：LLM 潤飾與辭典系統

- [ ] LLM 潤飾引擎（本機 llama.cpp）
- [ ] API 服務整合（OpenAI 相容）
- [ ] 潤飾預覽對照介面
- [ ] 辭典管理（熱詞表 + 替換規則）
- [ ] 辭典集切換
- [ ] 辭典匯入/匯出

### Phase 5：打磨與發佈（2 週）

> 目標：品質保證與跨平台打包

- [ ] 跨平台完整測試（Windows / macOS / Linux）
- [ ] 效能最佳化（記憶體、延遲）
- [ ] PyInstaller / Nuitka 打包
- [ ] 安裝程式製作（Windows: NSIS, macOS: DMG, Linux: AppImage）
- [ ] 使用者文件與教學
- [ ] Beta 測試

---

## 12. 風險評估與對策

| 風險 | 影響 | 可能性 | 對策 |
|------|------|--------|------|
| **macOS 輔助使用權限取得困難** | 快捷鍵和焦點管理無法運作 | 高 | 首次啟動引導使用者授權；提供圖文教學 |
| **Wayland 下快捷鍵/焦點管理受限** | Linux Wayland 環境無法正常使用 | 中 | 偵測 Wayland 並提示使用者切換 X11；持續追蹤 Wayland 生態發展 |
| **ASR 中文辨識品質不穩定** | 專業術語辨識錯誤率高 | 中 | Qwen3-ASR 上下文偏置注入熱詞；Breeze-ASR-25 台灣華語備選；辭典替換規則兜底；LLM 同音字修正 |
| **LLM 潤飾延遲過高** | 端到端體驗不佳 | 中 | 預設關閉 LLM；使用輕量模型（1.5B）；設定逾時機制（3s 回傳原文） |
| **剪貼簿方案被其他應用干擾** | 注入的文字不正確或剪貼簿內容遺失 | 低 | 備份/還原機制；在注入期間鎖定（~200ms 極短時間） |
| **PySide6 跨平台 UI 表現不一致** | 不同 OS 上膠囊外觀差異 | 低 | 自繪 UI（QPainter）而非依賴系統 Widget |
| **模型檔案過大影響首次體驗** | 使用者需等待下載 1.2GB+ 模型 | 中 | 預設使用 Qwen3-ASR-0.6B（~1.2GB）；背景下載；顯示進度；提供 SenseVoice（200MB）作為超輕量替代 |
| **Qwen3-ASR 需要 GPU 以獲最佳效能** | 無 GPU 設備體驗不佳 | 中 | 0.6B 版本 CPU 可接受；無 GPU 時自動推薦 SenseVoice/Paraformer（sherpa-onnx CPU 最佳化）；首次啟動偵測硬體並推薦模型 |
| **Qt Event Loop 與 pynput 衝突** | 程式崩潰或快捷鍵無回應 | 低 | pynput 在獨立 daemon thread 運行；透過 Qt Signal 跨執行緒通訊 |

---

## 13. 附錄

### 附錄 A：UI 參考設計

浮動膠囊設計參考：深色半透明膠囊，包含 7 根動態音波柱（藍白漸層）、分隔線、麥克風按鈕（含聆聽狀態指示）、以及裝置選擇下拉箭頭。膠囊下方顯示當前狀態文字（如 LISTENING...）。

互動 Prototype 位於專案 `prototype/airtype-ui-prototype.jsx`。

### 附錄 B：相依套件

**核心依賴**

| 套件 | 版本 | 用途 |
|------|------|------|
| PySide6 | ≥ 6.6.0 | GUI 框架 |
| pynput | ≥ 1.7.6 | 全域快捷鍵 |
| sounddevice | ≥ 0.4.6 | 音訊 I/O |
| numpy | ≥ 1.24.0 | 音訊數值處理 |
| qwen-asr | latest | Qwen3-ASR 推理引擎（首選 ASR） |
| onnxruntime | ≥ 1.16.0 | ONNX 推理（VAD + sherpa-onnx 模型） |
| pyperclip | ≥ 1.8.2 | 剪貼簿操作 |
| pyautogui | ≥ 0.9.54 | 模擬鍵盤輸入 |

**可選依賴**

| 套件 | 版本 | 用途 |
|------|------|------|
| transformers | ≥ 4.40.0 | Breeze-ASR-25 推理（HuggingFace pipeline） |
| faster-whisper | ≥ 1.0.0 | Breeze-ASR-25 / Whisper 系列加速推理 |
| sherpa-onnx | ≥ 1.9.0 | SenseVoice / Paraformer 輕量引擎 |
| vllm | latest | Qwen3-ASR 串流推理後端 |
| torch + torchaudio | ≥ 2.0.0 | Breeze-ASR-25 音訊前處理 |
| llama-cpp-python | ≥ 0.2.0 | 本機 LLM 推理 |
| keyring | ≥ 24.0.0 | API Key 加密儲存 |
| noisereduce | ≥ 3.0.0 | 軟體降噪 |

### 附錄 C：競品參考

| 產品 | 優勢 | 限制 | Airtype 對應策略 |
|------|------|------|----------------|
| Windows 語音輸入 | 系統原生整合 | 僅 Windows；雲端依賴 | 跨平台 + 離線 |
| macOS 聽寫 | 系統原生整合 | 僅 macOS；進階功能需雲端 | 跨平台 + 可自訂 |
| Qwen3-ASR (API) | 商業 API 品質極高 | 需網路；按量計費 | 整合開源本機版作為 ASR 核心 |
| Whisper.cpp | 開源高品質 | 無 UI；無注入功能；台灣華語非最佳 | 整合 Breeze-ASR-25 作為台灣華語備選 |
| Talon Voice | 強大的語音控制 | 學習曲線陡峭 | 聚焦文字輸入，簡單易用 |
| Notta / Otter.ai | 功能豐富 | 需要網路；隱私顧慮 | 完全離線；資料不離開設備 |

---

> **文件結尾**
>
> 本 PRD 為 Airtype 空音輸入的完整產品需求規格。隨開發進展，各章節將持續更新。所有技術決策需經過跨平台可行性驗證後才納入正式規格。
