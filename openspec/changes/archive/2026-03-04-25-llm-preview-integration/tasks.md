## 1. TDD 失敗測試

- [x] 1.1 在 `tests/test_controller.py` 撰寫失敗測試：PolishEngine Dependency Injection into CoreController — 驗證 `polish_engine=None` 時不呼叫 PolishEngine；`no polish_engine` 場景、`polish disabled` 場景
- [x] 1.2 在 `tests/test_controller.py` 撰寫失敗測試：LLM Polish Integration in Recognition Pipeline — 驗證 `polish enabled no preview` 場景（呼叫 polish 並直接注入）、`polish failure fallback` 場景（PolishError → 注入原始文字）
- [x] 1.3 在 `tests/test_controller.py` 撰寫失敗測試：Polish Preview Dialog Integration — 驗證 `user selects polished text`、`user selects original text`、`user dismisses dialog` 三個場景

## 2. CoreController 整合

- [x] 2.1 在 `airtype/core/controller.py` 的 `CoreController.__init__()` 新增 `polish_engine` 選用參數，實作 PolishEngine 透過建構子注入 CoreController 設計決策 — 驗證：PolishEngine Dependency Injection into CoreController 需求
- [x] 2.2 在 `CoreController` 實作 `on_recognition_complete()` 方法（或更新現有方法），在 PROCESSING 狀態中呼叫 `PolishEngine.polish()` 並處理失敗回退（潤飾流程在 on_recognition_complete() 中同步執行），失敗時靜默 fallback 至原始文字 — 驗證：LLM Polish Integration in Recognition Pipeline 需求
- [x] 2.3 在 `on_recognition_complete()` 中整合 PolishPreviewDialog 由 controller 在 Qt 主執行緒呼叫，依 `preview_before_inject` 選擇注入版本 — 驗證：Polish Preview Dialog Integration 需求
