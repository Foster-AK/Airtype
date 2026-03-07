## Why

Change 17（17-llm-polish）已實作 `PolishEngine` 與 `PolishPreviewDialog`，但兩者未連接至核心辨識管線（`CoreController`），導致 LLM 潤飾功能無法在實際使用流程中發揮作用。

## What Changes

- `CoreController` 接受 `PolishEngine` 依賴注入，在 PROCESSING → INJECTING 轉換時執行潤飾
- 若 `config.llm.enabled=True` 且 `config.llm.preview_before_inject=True`，顯示 `PolishPreviewDialog` 供使用者選擇原始或潤飾版本
- 若 `config.llm.enabled=True` 且 `config.llm.preview_before_inject=False`，直接使用潤飾結果進行注入
- 潤飾失敗（`PolishError` / 逾時）時靜默回退至原始文字，注入流程不中斷

## Capabilities

### New Capabilities

- `llm-pipeline-integration`: LLM 潤飾引擎整合至核心辨識管線，含 preview 選擇流程

### Modified Capabilities

（無——不修改 PolishEngine、PolishPreviewDialog 或 ASR 管線的規格）

## Impact

- 相依性：13-core-controller（CoreController 狀態機）、17-llm-polish（PolishEngine、PolishPreviewDialog）
- 受影響程式碼：
  - `airtype/core/controller.py`（注入 PolishEngine，新增潤飾流程）
  - `tests/test_controller.py`（新增整合測試）
