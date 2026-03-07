## 為什麼

使用者需要各平台可安裝的套件。此變更建立單一執行檔與各平台專屬安裝程式，並加入更新檢查機制。

參考：PRD §7.1（技術堆疊 — 打包）、§11 第 5 階段。

相依性：所有前序變更。

## 變更內容

- PyInstaller 或 Nuitka 建置配置，用於產生單一執行檔
- Windows：NSIS 安裝程式（.exe）
- macOS：含拖曳至 Applications 的 DMG
- Linux：AppImage
- 應用程式內更新檢查（HTTPS 版本 manifest，不自動安裝）

## 功能

### 新增功能

- `packaging`：跨平台應用程式打包與發行

### 修改功能

（無）

## 影響

- 新增檔案：`build/`、`installer/`、`airtype.spec`（PyInstaller）、建置腳本
- 相依於：所有前序變更
