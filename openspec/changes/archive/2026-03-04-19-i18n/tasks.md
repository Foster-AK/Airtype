## 1. 翻譯系統

- [x] 1.1 建立 `airtype/utils/i18n.py` 實作 `tr(key)` 函式與 JSON 翻譯檔載入 — 驗證：翻譯系統需求、JSON 架構翻譯檔需求
- [x] 1.2 實作以 Signal 為基礎的語言變更通知，支援執行期間語言切換 — 驗證：執行期間語言切換需求

## 2. 翻譯檔

- [x] 2.1 建立 `locales/zh_TW.json` 包含所有 UI 字串（預設 / 完整）
- [x] 2.2 建立 `locales/zh_CN.json`、`locales/en.json`、`locales/ja.json` 翻譯檔
- [x] 2.3 將所有現有 UI 字串包裹於 `tr()` 呼叫中，涵蓋所有 UI 檔案

## 3. 測試

- [x] 3.1 撰寫 tr() 函式單元測試（key 查詢、退回鏈、缺少 key）
- [x] 3.2 撰寫執行期間語言切換單元測試（Signal 發出、元件刷新）
