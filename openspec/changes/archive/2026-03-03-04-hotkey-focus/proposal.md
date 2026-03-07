## 為什麼

全域快捷鍵讓使用者能從任何應用程式觸發語音輸入，無需切換視窗。焦點管理記錄並還原作用中視窗，使文字注入能準確送達正確的應用程式。此變更為 text-injector（05）與 core-controller（13）的前置需求。

參考：PRD §4.3（快捷鍵規格）、§6.5（焦點管理）、§7.2（跨平台規格）。

相依性：01-project-setup。

## 變更內容

- 建立 `airtype/core/hotkey.py`，實作於 daemon thread 中執行的 pynput 全域快捷鍵監聽器
- 建立 `airtype/utils/platform_utils.py`，實作跨平台焦點管理（記錄與還原前景視窗）
- 實作從設定 shortcuts 區段讀取按鍵組合並進行解析的快捷鍵註冊
- 實作切換行為（按一次開始、再按一次停止）與取消快捷鍵（Escape）
- 將 `pynput` 加入專案依賴
- 建立 `tests/test_hotkey.py`，包含單元測試與整合測試

## 功能

### 新增功能

- `global-hotkey`：透過 pynput 實現的系統級快捷鍵監聽器，支援跨平台（Windows、macOS、Linux）。從設定註冊可設定的按鍵組合，支援切換與取消行為。
- `focus-management`：跨 Windows（Win32 API）、macOS（osascript/AppKit）與 Linux（xdotool）記錄並還原前景視窗。封裝於 platform_utils.py 中的 FocusManager 介面之後。

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/hotkey.py`、`airtype/utils/platform_utils.py`、`tests/test_hotkey.py`
- 新增依賴：`pynput`
- 相依：01-project-setup（設定、專案結構）
