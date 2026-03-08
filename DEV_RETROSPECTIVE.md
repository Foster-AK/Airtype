# Airtype v2.0 開發回顧總結

## 專案概況

| 指標 | 數值 |
|------|------|
| 開發時間 | 2026-03-03 ~ 2026-03-08（**6 天**） |
| Git 提交 | 6 次 |
| 源碼行數 | ~15,200 行（40 個 Python 模組） |
| 測試行數 | ~15,100 行（31 個測試檔案） |
| 規範文件 | 42 份 spec |
| 封存變更 | 50 個（22 個主功能 + 3 個補充 + 25 個 bug 修復） |
| 多語系 | 4 種（繁中/簡中/英/日） |

---

## 做得好的地方

### 1. Spec-Driven Development (SDD) 流程紮實

22 個 change 每個都走完 proposal → design → specs → tasks 四層 artifact，先設計再實作。這讓 50 個變更都有清晰的追溯性，每個功能的「為什麼」和「怎麼做」都有文件記錄。這是整個專案最大的優勢——即使日後回頭看，也能快速理解每個決策的脈絡。

### 2. 測試覆蓋率接近 1:1

15K 行源碼配 15K 行測試，比例非常健康。31 個測試檔案涵蓋了核心引擎、UI 元件、管線、控制器等所有關鍵模組。這在快速開發週期中尤其難得。

### 3. 模組化架構設計良好

- `core/`（17 個模組）、`ui/`（14 個模組）、`utils/`（9 個模組）職責清晰
- ASR 引擎抽象層支援 5 種引擎（Qwen OpenVINO / PyTorch CUDA / Vulkan / Breeze / sherpa-onnx）無縫切換
- 控制器狀態機 + 事件分發是典型的乾淨架構

### 4. Bug 修復有紀律

25 個 bug 修復全部走 OpenSpec 流程封存，不是隨手 patch。這保持了整個 change history 的一致性。

### 5. 跨平台 + 多語系一步到位

Windows/macOS/Linux 三平台 + 四語言在初始設計就考慮進去，而非事後追加，避免了大量重構。

---

## 做得不好的地方

### 1. 巨型提交，Git 歷史幾乎無法追溯（最嚴重）

6 天只有 6 次提交，第一次提交就包含了「大量規格文件、LLM 工具與核心組件、VAD 模型、安裝程式資源、測試與本地化檔案」——基本是把整個專案一次 dump 進 repo。後續提交也是大批量的。這意味著：

- 無法用 `git bisect` 定位問題
- 無法看出功能的演進過程
- Code review 幾乎不可能
- 如果需要 revert 某個功能，粒度太粗

### 2. 開發速度過快，實際整合測試不足

6 天完成 22 個主功能 + 50 個變更，速度驚人但也令人擔憂。每個模組都有 unit test，但端到端的整合測試（真正打開麥克風 → VAD → ASR → LLM 潤飾 → 文字注入的完整鏈路）很可能不充分。Spec 和 test 都通過不代表實際使用沒問題。

### 3. 巨大的首次 commit 暗示「先寫完再提交」的工作模式

這表示開發過程中沒有持續整合（CI）、沒有分支策略、沒有 PR review。所有程式碼都在 `main` 上直接開發。對一人專案來說勉強可以接受，但如果未來要協作，這個習慣必須改。

### 4. OpenSpec change 封存時 spec 同步的可靠性存疑

開發過程中遇到 delta spec 格式問題（舊版中文格式不被接受）和 archive 時 specs/ 格式錯誤導致失敗的情況。這表示 Spectra 工具鏈本身還不夠穩定，或是在快速迭代中規範格式沒有一開始就統一好。

### 5. 換行符不一致（LF/CRLF）

多個檔案有 LF/CRLF 警告。這是 Windows 開發常見問題，但應該在專案初始化時用 `.gitattributes` 統一處理，而非事後修補。

### 6. 所有 bug 修復集中在功能完成後（03-05 ~ 03-08）

25 個 bug 修復中很多是 UI 問題（不透明度、checkbox 渲染、滾動條、導航焦點）。這暗示 UI 開發階段缺乏即時的視覺驗證——可能是先寫了 UI 程式碼和 test，但沒有實際跑起來看效果。

---

## 未來改善建議

### 短期（立即可做）

#### A. 建立 `.gitattributes` 統一換行符

在專案根目錄建立 `.gitattributes` 檔案，設定所有文字檔案統一使用 LF，一勞永逸解決 LF/CRLF 問題。

#### B. 寫一份端到端整合測試

模擬完整的語音輸入 → VAD → ASR → LLM 潤飾 → 文字注入鏈路，即使用 mock 音訊資料也好。確保各模組串接後的行為符合預期。

#### C. 設定 CI（GitHub Actions）

至少跑 `pytest` + linting（如 ruff），確保每次提交不破壞現有功能。

### 中期（下個開發週期）

#### D. 養成小步提交的習慣

每完成一個 OpenSpec change 就提交一次，commit message 對應 change 編號。例如：

```
feat(02): implement audio capture with ring buffer
feat(03): add Silero VAD v5 engine with 4-state machine
fix(ui): resolve capsule opacity not updating in realtime
```

50 個 change 至少應有 50 次提交。

#### E. 開發 UI 時加入視覺驗證環節

每完成一個 UI 元件就實際執行看效果，不要等全部寫完再一起測。Spectra 流程可以加一個「UI 截圖驗證」步驟。

#### F. 統一語言規範

目前 commit message 混用中英文。建議統一：

- Spec 文件：英文
- Commit message：英文
- UI 顯示文字：透過 i18n 系統處理
- 程式碼註解：英文

### 長期（架構層面）

#### G. 引入分支策略

即使是個人專案，用 `feature/xx-change-name` 分支開發 → PR 合併 → main 保持乾淨，未來協作時可無縫過渡。基本流程：

```
git checkout -b feature/02-audio-capture
# ... 開發 + 提交 ...
git checkout main
git merge feature/02-audio-capture
```

#### H. 建立 Integration Test Harness

建立一個可以在 CI 中執行的整合測試框架，用預錄音訊檔測試 VAD → ASR 管線的準確率回歸。避免修改某個模組後意外影響其他模組的行為。

#### I. Spectra 工具鏈穩定化

修正 delta spec 格式驗證的問題，讓 archive 流程更可靠，不需要手動 workaround（如臨時移除 specs 目錄）。

---

## 總體評價

這個專案展現了非常強的架構設計能力和規範驅動的開發紀律。42 份 spec、50 個封存 change、1:1 的測試比例——這些都是很多正式團隊專案都達不到的水準。

但最大的弱點在於**版本控制的實踐**。Git 只是被當作「備份工具」而非「開發歷史記錄器」使用。6 次巨型提交讓整個精心設計的 OpenSpec 變更歷史在 git 層面完全看不見。如果 spec 文件遺失，這段開發過程就無法重建。

**核心建議：下一個專案或下一輪迭代，把「每個 change 一個 commit」作為硬性規則。** 這一個改變就能解決大部分問題。
