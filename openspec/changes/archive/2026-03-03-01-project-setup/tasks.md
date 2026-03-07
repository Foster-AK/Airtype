## 1. 專案中繼資料與目錄骨架

- [x] 1.1 建立 `pyproject.toml` 搭配無 src 配置（依設計的無 src 配置 pyproject.toml）：專案中繼資料（name=airtype、version=0.1.0、python>=3.11、description、author）與空依賴清單 — 驗證：專案中繼資料需求
- [x] 1.2 依設計建立目錄骨架：`airtype/`、`airtype/core/`、`airtype/ui/`、`airtype/utils/` 各自包含 `__init__.py` — 驗證：目錄骨架需求
- [x] 1.3 建立資源與資料目錄：`models/`、`dictionaries/`、`resources/icons/`、`resources/sounds/`、`tests/` 搭配 `.gitkeep` 檔案 — 驗證：資源與資料目錄需求
- [x] 1.4 建立 `requirements.txt` 搭配開發依賴（pytest、pytest-cov）

## 2. 設定資料模型

- [x] 2.1 實作 `airtype/config.py`，以巢狀區段的 Python dataclass 作為 ConfigModel：`GeneralConfig`、`VoiceConfig`、`LlmConfig`、`DictionaryConfig`、`AppearanceConfig`、`ShortcutsConfig`，組合成 `AirtypeConfig` — 所有預設值符合 PRD §7.4 — 驗證：設定資料模型需求
- [x] 2.2 實作設定版本追蹤：頂層 `version` 欄位預設為 `"2.0"` — 驗證：設定版本追蹤需求
- [x] 2.3 實作 `to_dict()` 與 `from_dict()` 方法，用於 JSON 序列化往返，支援缺失欄位退回 — 驗證：設定序列化往返情境、載入缺少欄位的設定情境

## 3. 設定檔案持久化

- [x] 3.1 實作設定目錄自動建立：以 `pathlib.Path.home()` 跨平台建立 `~/.airtype/` 搭配 `0o700` 權限（若不存在）— 驗證：設定目錄初始化需求
- [x] 3.2 實作 JSON 檔案搭配原子寫入的持久化：`save()` 方法寫入暫存檔後執行 `os.replace()` — 驗證：設定檔案持久化需求、儲存設定情境
- [x] 3.3 實作 `load()` 方法：讀取既有設定 JSON、處理損毀設定（重新命名為 `.bak`、建立預設值）、處理缺失欄位 — 驗證：載入既有設定情境、載入損毀的設定情境

## 4. 結構化日誌記錄

- [x] 4.1 在 `airtype/__init__.py` 或專用 `airtype/logging_setup.py` 中實作 Python logging 模組搭配結構化格式：設定格式 `[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s`，等級從設定 `general.log_level` 讀取 — 驗證：結構化日誌記錄需求

## 5. Python 套件進入點

- [x] 5.1 建立 `airtype/__main__.py` 作為 Python 套件進入點：載入設定 → 設定日誌記錄 → 記錄啟動訊息 → 結束 — 驗證：Python 套件進入點需求
- [x] 5.2 驗證 `python -m airtype` 無錯誤執行，首次執行時建立 `~/.airtype/config.json` — 驗證：透過 python -m 啟動情境、無設定檔時啟動情境

## 6. 測試

- [x] 6.1 撰寫 `AirtypeConfig` 的單元測試：預設值、序列化往返、缺失欄位處理、損毀檔案恢復
- [x] 6.2 撰寫整合測試：乾淨環境 → `python -m airtype` → 驗證設定目錄與檔案已建立 → 結束碼 0
