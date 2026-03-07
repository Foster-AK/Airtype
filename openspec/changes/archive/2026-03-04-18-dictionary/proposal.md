## 為什麼

自訂辭典可提升 ASR 對特定領域術語的辨識精度。熱詞可提高辨識優先權；替換規則用於在 ASR 輸出後修正常見誤辨結果。辭典集則允許快速切換使用情境。

參考：PRD §5.5（辭典管理）、§5.5.1-5.5.4。

相依性：06-asr-abstraction、16-settings-panel。

## 變更內容

- 實作辭典引擎：熱詞清單 + 替換規則（字串與正規表達式）
- 實作辭典集（具名群組、多選啟用）
- 實作辭典 UI 設定頁面（可編輯表格、匯入/匯出）
- 透過 set_hot_words() 將熱詞串接至 ASR 引擎
- 支援 .txt/.csv/.json 匯入/匯出及 .airtype-dict 分享格式

## 功能

### 新增功能

- `dictionary-engine`：熱詞、替換規則及辭典集管理
- `dictionary-ui`：具備可編輯表格與匯入/匯出功能的辭典設定頁面

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/dictionary.py`、`airtype/ui/settings_dictionary.py`、`tests/test_dictionary.py`
- 相依於：06-asr-abstraction（熱詞介面）、16-settings-panel
