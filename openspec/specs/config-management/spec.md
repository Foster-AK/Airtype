# 規格：設定管理

## 概述

本規格定義 Airtype 應用程式設定系統的型別化設定資料模型、檔案持久化策略、目錄初始化，以及版本追蹤。

## 需求

### 需求：設定資料模型

系統應（SHALL）提供使用 Python `@dataclass` 類別的型別化設定模型，對應 PRD §7.4 所定義的 JSON schema。模型應（SHALL）包含以下區段：`GeneralConfig`、`VoiceConfig`、`LlmConfig`、`DictionaryConfig`、`AppearanceConfig`、`ShortcutsConfig`，組合成頂層 `AirtypeConfig`。

#### 情境：預設設定值

- **當** 以無參數方式實例化 `AirtypeConfig` 時
- **則** 所有欄位應（SHALL）具有符合 PRD §7.4 的預設值（例如 `general.language = "zh-TW"`、`general.silence_timeout = 1.5`、`voice.asr_model = "qwen3-asr-0.6b"`、`appearance.theme = "system"`）

#### 情境：設定序列化往返

- **當** `AirtypeConfig` 序列化為 JSON 後再反序列化回來時
- **則** 產生的物件應（SHALL）與原始物件相等

---
### 需求：設定檔案持久化

系統應（SHALL）將設定持久化至 `~/.airtype/config.json`。寫入應（SHALL）使用原子檔案操作（寫入暫存檔，然後 `os.replace()`）以防止損毀。

#### 情境：儲存設定

- **當** 呼叫 `config.save()` 時
- **則** 設定應（SHALL）以格式化 JSON（indent=2）使用原子寫入方式寫入 `~/.airtype/config.json`

#### 情境：載入既有設定

- **當** 應用程式啟動且 `~/.airtype/config.json` 存在並包含有效 JSON 時
- **則** 系統應（SHALL）載入並解析檔案為 `AirtypeConfig` 實例

#### 情境：載入損毀的設定

- **當** 應用程式啟動且 `~/.airtype/config.json` 包含無效 JSON 時
- **則** 系統應（SHALL）記錄警告、將損毀檔案重新命名為 `config.json.bak`，並建立新的預設設定

#### 情境：載入缺少欄位的設定

- **當** 設定檔缺少某些欄位（例如較舊版本的設定）時
- **則** 系統應（SHALL）以預設值填補缺失欄位並正常繼續

---
### 需求：設定目錄初始化

系統應（SHALL）在 `~/.airtype/` 目錄不存在時以權限 `0o700`（僅限使用者存取）建立該目錄。在 Windows 上，目錄應（SHALL）建立於 `%USERPROFILE%/.airtype/`。

#### 情境：首次執行建立設定目錄

- **當** 應用程式首次啟動且 `~/.airtype/` 不存在時
- **則** 系統應（SHALL）以受限權限建立 `~/.airtype/` 並寫入預設設定檔

#### 情境：設定目錄已存在

- **當** 應用程式啟動且 `~/.airtype/` 已存在時
- **則** 系統不得（SHALL NOT）修改目錄權限

---
### 需求：設定版本追蹤

設定應（SHALL）在頂層包含 `version` 欄位（字串，預設 `"2.0"`）。此欄位應（SHALL）供未來變更用於偵測和遷移舊版設定格式。

#### 情境：輸出中包含版本欄位

- **當** 預設設定儲存至磁碟時
- **則** JSON 檔案應（SHALL）包含頂層 `"version": "2.0"` 欄位

## 變更歷史

| 變更 | 說明 |
|------|------|
| 01-project-setup | 初始規格 — 定義設定 dataclass 模型、持久化、目錄初始化與版本追蹤 |

## Requirements
