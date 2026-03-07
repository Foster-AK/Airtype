## 背景

Airtype v2.0 是一個全新的 Python + PySide6 專案。目前尚無任何程式碼。此變更建立基礎專案結構、設定系統與日誌記錄，所有後續 21 個變更皆依賴於此。專案目標為 Windows、macOS 與 Linux 桌面平台。

PRD 定義了詳細的目錄結構（§7.3）與設定 JSON schema（§7.4），此變更予以實作。

## 目標 / 非目標

**目標：**

- 建立可執行的 Python 套件（`python -m airtype`），能乾淨地啟動與結束
- 建立符合 PRD §7.3 的完整目錄骨架
- 實作帶有 JSON 持久化至 `~/.airtype/config.json` 的型別化設定模型
- 設定可設定等級的結構化日誌記錄
- 建立包含專案中繼資料與核心依賴的 `pyproject.toml`

**非目標：**

- 此變更不包含 PySide6 UI（屬於 14-overlay-ui 及後續變更）
- 不包含音訊、ASR、VAD 或 LLM 功能
- 不包含系統匣或快捷鍵註冊
- 不包含「啟動 → 載入設定 → 記錄日誌 → 結束」以外的實際應用邏輯

## 決策

### 以巢狀區段的 Python dataclass 作為 ConfigModel

使用 `@dataclass` 類別建模每個設定區段（GeneralConfig、VoiceConfig、LlmConfig、DictionaryConfig、AppearanceConfig、ShortcutsConfig），並以頂層 `AirtypeConfig` 組合它們。這精確對應 PRD §7.4 的 JSON 結構。

**為何選擇 dataclass 而非 Pydantic**：Pydantic 會增加沉重的依賴。設定 schema 相當直觀——不需要複雜的驗證或 schema 產生。Python `dataclass` 已足夠。

**為何不使用 TypedDict**：dataclass 提供預設值、用於驗證的 `__post_init__`，以及更好的 IDE 支援。

**為何使用自訂 `to_dict()` 而非 `dataclasses.asdict()`**：`DictionaryConfig.hot_words` 和 `replace_rules` 儲存為 `list[dict]`（原始 JSON 相容的 dict），而非巢狀 dataclass。`dataclasses.asdict()` 在此可正常運作，但透過迭代 `__dataclass_fields__` 的自訂 `to_dict()` 同樣正確、避免標準函式庫 import，且使輸出結構更明確。`HotWord`/`ReplaceRule` 型別化 dataclass 刻意延後至 18-dictionary 的完整辭典管理中實作。

### JSON 檔案搭配原子寫入實現持久化

設定儲存於 `~/.airtype/config.json`。寫入使用暫存檔 + `os.replace()` 確保原子性——防止程序在寫入中途崩潰時損毀檔案。

**為何選擇 JSON 而非 TOML/YAML**：PRD §7.4 明確指定 JSON。且為標準函式庫（`json` 模組），零依賴。

### 設定目錄自動建立

首次執行時，依 PRD §9.3 以模式 `0o700`（僅限使用者存取）建立 `~/.airtype/`。子目錄（`models/`、`dictionaries/`）在後續變更需要時延遲建立。

### Python logging 模組搭配結構化格式

使用標準函式庫 `logging` 搭配一致格式：`[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s`。日誌等級可透過設定設定（`general.log_level`）。預設輸出至 stderr；檔案日誌記錄延後至後續變更。

**為何不使用 loguru/structlog**：基礎設施零外部依賴。若後續需要結構化 JSON 日誌記錄，可再遷移。

### pyproject.toml 搭配無 src 配置

直接使用 `airtype/` 作為套件目錄（而非 `src/airtype/`）。這符合 PRD §7.3 結構。套件可透過 `python -m airtype` 執行。

## 風險 / 取捨

- [風險] dataclass 設定模型缺乏未來設定格式變更的 schema 遷移 → 緩解措施：在設定中包含 `version` 欄位。未來變更可偵測並遷移舊版設定。
- [風險] `~/.airtype/` 路徑偏向 Unix；Windows 使用 `%APPDATA%` → 緩解措施：使用在所有平台皆可運作的 `pathlib.Path.home() / ".airtype"`。點號前綴慣例在 Windows 上也可使用。
- [取捨] 設定載入時無執行時型別檢查（dataclass 不驗證來自 JSON 的型別）→ 目前可接受；若需要可在 20-security-audit 中加入驗證。
