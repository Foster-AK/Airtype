# 規格：專案結構

## 概述

本規格定義 Airtype 應用程式的目錄配置、套件骨架、專案中繼資料，以及日誌記錄設定。

## 需求

### 需求：Python 套件進入點

系統應（SHALL）在 `airtype/__main__.py` 提供可執行的 Python 套件進入點，允許透過 `python -m airtype` 啟動應用程式。

#### 情境：透過 python -m 啟動

- **當** 使用者從專案根目錄執行 `python -m airtype` 時
- **則** 應用程式應（SHALL）無錯誤啟動並記錄初始化訊息

#### 情境：無設定檔時啟動

- **當** 應用程式啟動且 `~/.airtype/config.json` 不存在時
- **則** 應用程式應（SHALL）建立設定目錄與預設設定檔，然後正常啟動

---
### 需求：目錄骨架

系統應（SHALL）在專案初始化時建立以下套件目錄：`airtype/core/`、`airtype/ui/`、`airtype/utils/`。每個目錄應（SHALL）包含 `__init__.py` 檔案。

#### 情境：套件目錄存在

- **當** 專案已設定完成時
- **則** `airtype/`、`airtype/core/`、`airtype/ui/`、`airtype/utils/` 應（SHALL）各自包含 `__init__.py` 檔案，使其成為可匯入的 Python 套件

---
### 需求：資源與資料目錄

專案應（SHALL）在儲存庫中包含以下非程式碼目錄：`models/`、`dictionaries/`、`resources/icons/`、`resources/sounds/`、`tests/`。

#### 情境：資源目錄存在

- **當** 專案被 clone 或初始化時
- **則** 目錄 `models/`、`dictionaries/`、`resources/icons/`、`resources/sounds/`、`tests/` 應（SHALL）存在（空目錄以 `.gitkeep` 檔案保留）

---
### 需求：專案中繼資料

專案應（SHALL）具有 `pyproject.toml` 檔案，定義專案名稱（`airtype`）、版本、Python 版本需求（`>=3.11`），以及核心依賴。

#### 情境：安裝專案

- **當** 開發者在專案根目錄執行 `pip install -e .` 時
- **則** `airtype` 套件應（SHALL）以可編輯套件形式安裝且無錯誤

---
### 需求：結構化日誌記錄

應用程式應（SHALL）在啟動時設定 Python 標準函式庫 `logging`，格式為 `[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s`。日誌等級應（SHALL）可透過設定檔的 `general.log_level` 設定，支援值：DEBUG、INFO、WARNING、ERROR。

#### 情境：預設日誌等級

- **當** 應用程式以預設設定啟動時
- **則** 日誌等級應（SHALL）設為 INFO

#### 情境：自訂日誌等級

- **當** 設定檔的 general 區段包含 `"log_level": "DEBUG"` 時
- **則** 應用程式應（SHALL）將根日誌記錄器等級設為 DEBUG

## 變更歷史

| 變更 | 說明 |
|------|------|
| 01-project-setup | 初始規格 — 定義專案配置、進入點、中繼資料與日誌記錄 |

## Requirements
