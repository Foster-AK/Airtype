## 1. 建置配置

- [x] 1.1 建立 PyInstaller `.spec` 檔案作為主要建置工具配置，用於產生單一執行檔 — 驗證：單一執行檔需求、以 PyInstaller 作為主要建置工具的設計決策
- [x] 1.2 在 `build/` 目錄下建立各平台專屬建置腳本 — 驗證：各平台專屬建置腳本需求

## 2. 各平台安裝程式

- [x] 2.1 使用 NSIS 建立 Windows 安裝程式 — 驗證：Windows 安裝程式需求
- [x] 2.2 建立含拖曳至 Applications 的 macOS DMG — 驗證：macOS DMG 需求
- [x] 2.3 建立 Linux AppImage — 驗證：Linux AppImage 需求

## 3. 更新機制

- [x] 3.1 實作透過 JSON 端點進行 HTTPS 版本 manifest 更新檢查 — 驗證：透過 HTTPS 版本 manifest 進行更新檢查需求

## 4. 測試

- [x] 4.1 撰寫冒煙測試：建置 → 啟動 → 驗證啟動成功 → 結束
