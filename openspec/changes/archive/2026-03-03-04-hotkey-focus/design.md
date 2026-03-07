## 背景

Airtype 需要系統級快捷鍵，讓使用者能從任何應用程式觸發語音輸入，無需切換視窗。辨識完成後，系統必須將焦點還原至原始視窗，使文字注入能送達正確位置。此變更提供快捷鍵監聽器與焦點管理基礎設施，供 text-injector（05）與 core-controller（13）構建其上。

相依性：01-project-setup（設定模型、專案結構）。

## 目標 / 非目標

**目標：**

- 使用 pynput 在 daemon thread 中實作全域快捷鍵監聽器
- 支援從設定 shortcuts 區段讀取的可設定按鍵組合
- 實作切換行為（按一次開始、再按一次停止）與取消（Escape）
- 在 Windows、macOS 與 Linux 上記錄並還原前景視窗
- 提供抽象化平台差異的乾淨 FocusManager 介面

**非目標：**

- 不進行音訊擷取或 ASR 觸發（屬於 02-audio-capture、03-vad-engine 及後續變更）
- 不進行文字注入（屬於 05-text-injector）
- 不包含 UI 元素（系統匣、浮動視窗——屬於後續變更）
- 不支援 Wayland（此變更中 Linux 僅限 X11）

## 決策

### pynput 監聽器於 daemon thread 中執行

pynput 在背景 daemon thread 中執行自己的事件迴圈。與主應用程式的通訊透過執行緒安全的 callback queue。daemon thread 確保監聽器不會阻塞主執行緒或與 Qt 事件迴圈衝突（待後續加入 PySide6 時）。

**為何不使用 `keyboard` 函式庫**：pynput 在全部三個目標平台（Windows、macOS、Linux）上提供更好的跨平台支援。`keyboard` 函式庫在 Linux 上需要 root 權限，且 macOS 支援不一致。

**為何使用 daemon thread**：daemon thread 在主程序結束時自動終止，防止孤立的監聽器執行緒。pynput 的 `Listener` 類別專為執行緒設計，提供 `start()` / `stop()` 生命週期方法。

### 平台特定焦點管理

Windows 使用 `ctypes.windll.user32`（GetForegroundWindow / SetForegroundWindow 搭配 AttachThreadInput 實現可靠的焦點切換）。macOS 使用 `osascript` 透過 AppleScript 查詢並啟動應用程式（基於 NSWorkspace）。Linux 使用 `xdotool` 進行 X11 視窗管理（getactivewindow / windowactivate）。

所有平台特定實作都封裝於 `platform_utils.py` 中的 `FocusManager` 抽象介面之後。這讓核心控制器與文字注入器無需了解平台細節即可使用焦點管理。

**為何在 Windows 上使用 ctypes 而非 pywin32**：ctypes 為標準函式庫——無需額外依賴。所需的 Win32 API 呼叫（GetForegroundWindow、SetForegroundWindow、GetWindowThreadProcessId、AttachThreadInput）足夠簡單，適合使用 ctypes。

**為何在 macOS 上使用 osascript 而非 PyObjC**：osascript 在 macOS 上始終可用。PyObjC 是一個龐大的依賴。對於所需的簡單操作（取得最前方應用程式、啟動應用程式），osascript 已足夠。

### 從設定註冊快捷鍵

按鍵組合從 `config.shortcuts` 讀取（例如 `toggle_voice: "ctrl+shift+space"`）。快捷鍵模組將這些字串解析為 pynput key sets。支援的修飾鍵：ctrl、shift、alt、cmd/super。toggle_voice 的預設快捷鍵為 Ctrl+Shift+Space。

**為何使用字串式按鍵組合**：符合 PRD §7.4 的設定 JSON 格式。方便後續在 UI 設定中顯示。使用 pynput 的 `Key` 與 `KeyCode` 列舉進行解析十分直觀。

### 快捷鍵模組中的切換狀態機

快捷鍵 callback 維護一個簡單的二狀態切換：INACTIVE 與 ACTIVE。第一次按下轉換至 ACTIVE（觸發 start callback），第二次按下轉換至 INACTIVE（觸發 stop callback）。Escape 鍵觸發 cancel callback，並無論目前狀態為何，皆重設為 INACTIVE。

**為何採用切換而非按住說話**：PRD §4.3 指定切換為預設模式。按住說話可作為替代模式於後續加入。

## 風險 / 取捨

- [風險] macOS 需要輔助使用權限才能讓 pynput 擷取全域快捷鍵 → 緩解措施：偵測權限缺失，記錄清晰的錯誤訊息並提供啟用指示（系統偏好設定 > 隱私權與安全性 > 輔助使用）。優雅降級，不崩潰。
- [風險] Linux 上的 Wayland 不支援 xdotool 焦點管理 → 緩解措施：文件記載 X11 需求。Wayland 支援延後至未來變更。若偵測到 Wayland 則記錄警告。
- [風險] pynput 可能在某些平台上與 PySide6 Qt 事件迴圈衝突 → 緩解措施：於 daemon thread 中執行 pynput 以隔離事件迴圈。callback 使用執行緒安全機制（queue 或 signal）通訊。
- [取捨] Windows 上 SetForegroundWindow 在呼叫程序非前景程序時可能不可靠 → 緩解措施：使用 AttachThreadInput 技巧，在呼叫 SetForegroundWindow 前暫時附加至目標視窗的執行緒。
