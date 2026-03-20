## Context

Airtype 啟動時 ASR 引擎初始化在 Windows 和 macOS 上都失敗（`asr_engine=None`），但根因不同：

- **macOS**：PyInstaller 打包的 `.app` 不包含 ASR 引擎模組（動態 `importlib.import_module()` 不被 PyInstaller 追蹤）
- **Windows**：模型目錄存在但檔案不完整（下載中斷），現有程式碼不驗證檔案完整性
- **共通**：引擎載入失敗的日誌級別太低（debug），且 `load_default_engine` 靜默失敗被外層誤判為成功

現有程式碼位置：
- `airtype/__main__.py:184-199`：ASR 引擎動態登錄 + `load_default_engine`
- `airtype/__main__.py:342-353`：ASR 缺失警告對話框
- `airtype/utils/model_manager.py:281-300`：`is_downloaded()` 只檢查目錄存在
- `airtype/core/asr_qwen_onnx.py:295-370`：`load_model()` 已有 `FileNotFoundError` 但是延遲觸發
- `airtype.spec:31-42`：`hiddenimports` 未包含引擎模組

## Goals / Non-Goals

**Goals:**

- 修復 macOS 打包後 ASR 引擎模組缺失
- 在啟動階段提前偵測模型檔案不完整
- 提供有用的診斷資訊（缺少哪些檔案、是否有未完成的下載）
- 修正引擎載入成功/失敗的判斷邏輯

**Non-Goals:**

- 不自動修復不完整的下載（使用者需手動重新下載）
- 不修改 `load_default_engine()` 的內部邏輯（只修改外層判斷）
- 不為所有引擎類型添加 `REQUIRED_FILES`（先只加 ONNX 引擎，其他按需補充）

## Decisions

### PyInstaller Hidden Imports 策略

在 `airtype.spec` 的 `hiddenimports` 加入全部 6 個 ASR 引擎模組和共用模組。各引擎的 `register()` 函式已有 `try: import xxx except ImportError: return False` 容錯，不會因依賴套件缺失而崩潰。

替代方案：使用 PyInstaller hook 檔案自動收集 `airtype.core` 下所有模組。但 hook 檔案較難維護，且可能引入不需要的模組，明確列出更安全。

### 模型完整性驗證架構

採用「引擎自我宣告 + ModelManager 驗證」模式：
- 各引擎類別定義 `REQUIRED_FILES: list[str]` 類別屬性（支援 `"A OR B"` 語法表示至少一個存在）
- `ModelManager.validate_model_files()` 接受 `required_files` 參數執行驗證
- 啟動時在 `load_default_engine` 前呼叫驗證，結果存入 `model_integrity_msg` 供警告對話框使用

替代方案：在 manifest.json 中定義 `required_files`。但這會增加 manifest 維護負擔，且引擎最了解自己需要什麼檔案。

### 引擎載入成功判斷修正

不修改 `load_default_engine()` 的內部行為（階段 4 仍保持 warning + return），而是在 `__main__.py` 中以 `asr_registry.active_engine is not None` 判斷實際結果。這避免破壞 `load_default_engine` 的容錯設計。

### 日誌級別提升

引擎模組載入失敗從 `logger.debug` 提升至 `logger.warning`，確保在預設 INFO 級別下可見。

## Risks / Trade-offs

- **[風險] 其他引擎缺少 REQUIRED_FILES**：目前只為 QwenOnnxEngine 定義，其他引擎的模型不完整時不會被預檢發現。→ 緩解：引擎自身的 `load_model()` 仍會在首次辨識時拋出 `FileNotFoundError`，預檢是額外的提前警告。
- **[風險] hiddenimports 增加打包體積**：加入引擎模組的原始碼（不含依賴套件）體積極小（幾十 KB），可忽略。
- **[權衡] warning 日誌可能在正常情況下也出現**：例如 macOS 上 `asr_qwen_pytorch`（需 torch）載入失敗是預期行為，但現在會顯示 WARNING。→ 可接受，因為這提供了有用的診斷資訊，且不影響功能。
