## 背景

使用者需要可安裝的執行檔。PRD 指定使用 PyInstaller/Nuitka 進行建置，並提供各平台專屬安裝程式。

相依性：所有前序變更。

## 目標 / 非目標

**目標：**

- 透過 PyInstaller 產生單一執行檔
- Windows NSIS 安裝程式
- macOS 含拖曳至 Applications 的 DMG
- Linux AppImage
- 用於更新檢查的版本 manifest

**非目標：**

- 不自動更新（僅檢查並通知）
- 不上架應用程式商店

## 決策

### 以 PyInstaller 作為主要建置工具

對 PySide6 應用程式而言，PyInstaller 比 Nuitka 更成熟且經過更廣泛的測試。使用 `.spec` 檔案進行配置。

**不選用 Nuitka 的原因**：編譯時間較長；PySide6 相容性測試較不充分。

### 各平台專屬建置腳本

每個平台在 `build/` 目錄下各有一份建置腳本：`build_windows.bat`、`build_macos.sh`、`build_linux.sh`。CI 可直接執行這些腳本。

### HTTPS 版本 manifest 用於更新檢查

`https://airtype.app/version.json` 包含最新版本、下載網址及更新日誌。應用程式於啟動時檢查（如已啟用通知）。不自動下載。

## 風險 / 取捨

- [風險] PyInstaller 打包檔可能被防毒軟體誤報 → 緩解措施：在 Windows 上進行程式碼簽署；說明誤報的處理方式
- [風險] macOS 需通過公證才能通過 Gatekeeper → 緩解措施：將公證流程納入建置腳本
- [取捨] 單一執行檔體積較大，但對使用者而言更簡便 → 為使用者體驗值得進行此取捨
