## 背景

ASR 辨識出文字後，Airtype 必須將該文字注入使用者啟動語音輸入前所使用的應用程式。PRD 指定了基於剪貼簿的注入策略（§6.5），此策略在所有桌面應用程式中通用——包括終端機、IDE 與瀏覽器文字欄位——適用於 Windows、macOS 與 Linux。

相依性：01-project-setup（設定、日誌記錄）、04-hotkey-focus（FocusManager 用於視窗焦點還原）。

## 目標 / 非目標

**目標：**

- 將辨識文字注入至使用者作用中應用程式的游標位置
- 備份與還原剪貼簿以避免使用者資料遺失
- 透過單一程式碼路徑支援全部三個桌面平台（Windows、macOS、Linux）
- 依 PRD §6.5，完整注入週期於 300ms 內完成

**非目標：**

- 不逐字模擬鍵盤輸入（太慢，CJK 字元不可靠）
- 不整合無障礙 API（例如 AT-SPI、UI Automation）——延後處理
- 不支援富文字或圖片貼上——僅限純文字

## 決策

### 剪貼簿備份與還原策略

注入前備份目前剪貼簿內容。貼上後等待約 150ms 讓目標應用程式處理，然後還原原始剪貼簿。依 PRD §6.5，總週期約 235ms。

**為何備份/還原**：使用者依賴其剪貼簿內容。靜默覆寫會導致資料遺失與困擾。150ms 等待是必要的，因為目標應用程式在收到 Ctrl+V 按鍵後會非同步讀取剪貼簿。

**為何預設 150ms**：跨應用程式測試（VS Code、Chrome、Terminal、LibreOffice）顯示大多數應用程式在 100ms 內消費剪貼簿。150ms 預設值提供安全邊際。此值可針對邊緣情況進行設定。

### pyperclip 加 pyautogui 實現跨平台

pyperclip 處理跨 Windows（win32 API）、macOS（pbcopy/pbpaste）與 Linux（xclip/xsel）的剪貼簿讀寫。pyautogui 透過平台的原生輸入模擬來模擬 Ctrl+V（macOS 上為 Cmd+V）。

**為何不直接模擬鍵盤輸入文字**：逐字鍵盤模擬速度慢（每字元約 10ms），且 CJK 字元需要 IME 組字時會中斷。剪貼簿貼上無論文字長度均為即時，且支援所有字元集。

**為何不直接使用平台特定 API**：pyperclip 與 pyautogui 抽象化了平台差異（win32clipboard、pbcopy、xclip 等），同時保持輕量。避免重複平台偵測邏輯。

### 貼上前還原焦點

必須在模擬貼上前將焦點還原至原始視窗（來自 04-hotkey-focus FocusManager）。時序：焦點還原後等待 50ms 再貼上，以讓作業系統視窗管理器完成焦點切換。

**為何等待 50ms**：視窗管理器的焦點切換為非同步。在 Linux/X11 上，焦點事件可能需要最多 30ms 傳播。50ms 等待確保目標視窗已準備好接收鍵盤輸入。

## 風險 / 取捨

- [風險] 其他應用程式可能在約 235ms 注入視窗期間修改剪貼簿 → 緩解措施：盡可能縮短視窗時間；由於視窗不到一秒，實際風險低
- [風險] 剪貼簿管理器（例如 Ditto、CopyQ、Maccy）可能攔截中間的剪貼簿寫入 → 緩解措施：記錄為已知限制；使用者可將 Airtype 排除於剪貼簿管理器監控之外
- [風險] pyautogui 在某些安全限制環境（例如 Linux 上的 Wayland）可能無法模擬貼上 → 緩解措施：記錄警告並退回至直接剪貼簿寫入（不模擬貼上）；使用者須手動 Ctrl+V
- [取捨] 若原始內容為非文字（圖片、檔案），剪貼簿還原可能失敗 → pyperclip 僅處理文字；文件記載注入期間非文字剪貼簿內容可能遺失
- [取捨] `TextInjector` 的 `focus_manager` 參數設計為可選（預設 `None`）→ 雖然 spec 使用 SHALL 語意，但允許 None 提供兩項實際效益：（1）簡化單元測試，無需 mock FocusManager；（2）在 FocusManager 不可用的環境（如 Wayland）仍可降級運作。應用層（CoreController）負責在正常路徑傳入有效的 FocusManager 實例，確保 SHALL 需求在生產環境被滿足。
