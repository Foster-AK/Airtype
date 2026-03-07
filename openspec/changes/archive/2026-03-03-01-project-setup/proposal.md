## 為什麼

Airtype 在任何功能開發開始之前需要基礎專案結構。此變更建立 Python 套件配置、帶有 JSON 持久化的設定模型，以及結構化日誌記錄——所有後續變更（02–22）皆依賴的共用基礎設施。沒有此變更，任何模組都無法獨立開發或測試。

參考：PRD §3.2（模組職責 — 核心控制器：設定管理）、§7.3（專案目錄結構）、§7.4（設定檔格式）。

## 變更內容

- 建立帶有 `__main__.py` 進入點的 `airtype/` Python 套件
- 依 PRD §7.3 建立完整目錄骨架（`core/`、`ui/`、`utils/`、`models/`、`dictionaries/`、`resources/`、`tests/`）
- 實作對應 PRD §7.4 JSON schema 的 `ConfigModel` dataclass（general、voice、llm、dictionary、appearance、shortcuts 區段）
- 實作設定持久化：從 `~/.airtype/config.json` 載入/儲存，搭配原子寫入與預設值退回
- 依 PRD §5.2 設定可設定日誌等級（DEBUG/INFO/WARN/ERROR）的結構化日誌記錄
- 建立包含核心依賴與專案中繼資料的 `pyproject.toml`
- 建立開發依賴用的 `requirements.txt`

## 功能

### 新增功能

- `project-structure`：Python 套件骨架、進入點（`python -m airtype`）與目錄配置
- `config-management`：設定 dataclass 模型、JSON 序列化/反序列化、原子檔案持久化與預設值

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/__init__.py`、`airtype/__main__.py`、`airtype/config.py`、`airtype/core/__init__.py`、`airtype/ui/__init__.py`、`airtype/utils/__init__.py`、`pyproject.toml`、`requirements.txt`
- 新增目錄：`airtype/`、`airtype/core/`、`airtype/ui/`、`airtype/utils/`、`models/`、`dictionaries/`、`resources/icons/`、`resources/sounds/`、`tests/`
- 外部依賴：無（此變更僅使用純 Python 標準函式庫）
- 此為基礎變更——所有後續 21 個變更皆依賴於此
