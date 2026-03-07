## Context

模型管理設定頁面（`SettingsModelsPage`）使用 QScrollArea 容納模型卡片列表。目前每張卡片採用 QHBoxLayout，左側為模型描述文字（stretch=1），右側為固定寬度 130px 的動作區（下載/進度/刪除按鈕，各 120px）。

設定視窗總寬度 720px，導覽列 160px，頁面內邊距 32px，卡片內邊距 24px + 間距 8px + 動作區 130px = 162px。左側文字區可用空間僅 366px，但部分模型描述（如「Qwen3-ASR 0.6B GGUF Q5_K_M（Vulkan / CPU 輕量路徑，由 OpenVoiceOS 提供）」）超過此寬度，導致水平 scrollbar 出現。

## Goals / Non-Goals

**Goals:**

- 消除模型管理頁面的水平 scrollbar
- 改善模型卡片的資訊層次：名稱與說明分行顯示
- 縮減按鈕留白，使操作區更緊湊

**Non-Goals:**

- 不重新設計整個設定視窗的佈局架構
- 不變更 manifest.json 中的描述格式
- 不修改模型下載/刪除的業務邏輯

## Decisions

### 禁用水平捲軸

在 `SettingsModelsPage._build_ui()` 中，對 QScrollArea 設定 `setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)`。

**理由**：模型管理頁面不需要水平捲動，所有內容應在可見區域內完整呈現。搭配描述拆行與按鈕縮減，卡片寬度不會超出 ScrollArea。

### 模型描述拆為雙行顯示

在 `ModelCardWidget._build_ui()` 中，以全形括號 `（` 為分割點，將 manifest description 拆為：

- 第一行（`_name_label`）：模型名稱，粗體 13px
- 第二行（`_desc_label`）：說明文字，灰色 11px，去除前後括號

若描述不含 `（`，則只顯示名稱行，說明行隱藏。

**理由**：相較於 wordWrap 自動折行，主動拆行可維持模型名稱的完整性與視覺層次。說明文字以灰色小字呈現，與既有的檔案大小 label 風格一致。

**替代方案**：使用 `setWordWrap(True)` 讓 QLabel 自動折行。缺點是折行位置不可控，可能在模型名稱中間斷行，影響可讀性。

### 縮減動作區與按鈕寬度

將右側動作區 `action_widget` 從 `setFixedWidth(130)` 改為 `setFixedWidth(90)`，所有按鈕與進度條從 `setFixedWidth(120)` 改為 `setFixedWidth(80)`。

**理由**：「下載」「取消」「刪除」等中文按鈕文字僅 2 字，120px 寬度留白過多。80px 足以容納文字並保有適當內邊距。

## Risks / Trade-offs

- **[風險] 極端視窗縮放**：若使用者大幅縮小視窗，左側文字區可能被壓縮至極窄寬度。→ 緩解：QLabel 預設會截斷（elide），且設定視窗有固定初始大小 720×520，使用者通常不會大幅縮小。
- **[風險] 未來新增無括號的描述**：若 manifest 新增不含 `（` 的描述，說明行將為空白。→ 緩解：程式碼已處理此情況，隱藏空白的說明 label。
- **[取捨] 按鈕寬度 80px**：若未來增加較長的按鈕文字（如其他語系），可能需要再調整。→ 緩解：i18n 翻譯時應控制按鈕文字長度。
