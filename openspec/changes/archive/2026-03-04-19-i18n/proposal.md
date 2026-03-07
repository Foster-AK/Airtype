## 為什麼

Airtype 面向國際用戶。UI 需要支援多種語言（zh-TW、zh-CN、en、ja），並可在執行期間切換。

參考：PRD §5.2（一般設定 — 語言下拉選單）。

相依性：16-settings-panel。

## 變更內容

- 使用 Python gettext 或自訂 JSON 架構的 i18n 實作翻譯系統
- 建立 zh-TW（預設）、zh-CN、en、ja 的翻譯檔
- 將所有 UI 字串串接至翻譯層
- 支援在不重新啟動的情況下於執行期間切換語言

## 功能

### 新增功能

- `i18n`：支援多語系 UI，可於執行期間切換語言

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/utils/i18n.py`、`locales/zh_TW.json`、`locales/zh_CN.json`、`locales/en.json`、`locales/ja.json`
- 修改：所有 UI 檔案（將字串包裹於 tr() 呼叫中）
- 相依於：16-settings-panel
