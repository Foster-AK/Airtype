## 背景

`CoreController`（Change 13）管理 6 個應用程式狀態（IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE）。PROCESSING 狀態完成後，`recognition_complete` 信號攜帶 ASR 辨識文字，接著直接進入 INJECTING。

`PolishEngine`（Change 17）與 `PolishPreviewDialog`（Change 17）已實作，但目前兩者未被 `CoreController` 引用。整合缺口在 PROCESSING → INJECTING 轉換之間。

## 目標 / 非目標

**目標：**

- 在 PROCESSING → INJECTING 之間插入可選的 LLM 潤飾步驟
- 支援 preview_before_inject 流程（顯示 dialog 等待使用者選擇）
- 潤飾失敗時靜默回退至原始文字

**非目標：**

- 不修改 `PolishEngine` 或 `PolishPreviewDialog` 實作
- 不修改 ASR 管線（Change 12）或 VAD 邏輯
- 不修改狀態轉換表（狀態仍為 PROCESSING → INJECTING）

## 決策

### PolishEngine 透過建構子注入 CoreController

在 `CoreController.__init__()` 新增可選參數 `polish_engine: Optional[PolishEngine] = None`。若為 `None`，視同 LLM 潤飾停用（等同 `config.llm.enabled=False`）。

優點：易於測試（直接注入 mock）；不改變現有建構子簽章的語義。

### 潤飾流程在 on_recognition_complete() 中同步執行

辨識完成後，在 PROCESSING 狀態內同步呼叫 `polish_engine.polish(text)`，完成後再轉換至 INJECTING。流程：

```
on_recognition_complete(text)
  → if polish enabled:
      polished = polish_engine.polish(text)   # 含逾時保護
      if preview_before_inject:
          chosen = PolishPreviewDialog(text, polished).exec()
      else:
          chosen = polished
  → transition(INJECTING)
  → text_injector.inject(chosen)
```

潤飾失敗（PolishError）時，`chosen = text`（原始文字），流程繼續。

### PolishPreviewDialog 由 controller 在 Qt 主執行緒呼叫

`PolishPreviewDialog.exec()` 為阻塞呼叫，必須在 Qt 主執行緒執行。由於 `on_recognition_complete` 預期由主執行緒透過 Qt Signal 觸發，此設計安全。

## 風險 / 取捨

- [風險] 潤飾逾時（3 秒）會延遲注入 → 緩解：`PolishEngine` 已內建逾時並回退至原始文字
- [取捨] 同步呼叫可能短暫阻塞 UI 主執行緒 → 可接受（最長 3 秒，有逾時上限）；未來可改為非同步
- [取捨] preview dialog 阻塞主執行緒等待使用者操作 → 為預期行為（modal dialog）
