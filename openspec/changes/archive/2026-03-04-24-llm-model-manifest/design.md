## Context

Change 11 的 `ModelManager` 實作了通用模型下載機制（進度回報、SHA-256 驗證、磁碟空間檢查），但 `models/manifest.json` 僅包含 ASR 模型條目，且缺少區分模型類型的欄位。Change 17（LLM 潤飾）在 design.md 明確委派模型下載至 Change 11，形成規格缺口。

相依性：11-model-hardware-mgr（`ModelManager` 複用）、17-llm-polish（讀取 manifest 欄位）。

## Goals / Non-Goals

**Goals：**

- 擴充 manifest schema，支援 LLM 模型類型宣告
- 加入 Qwen2.5 系列 GGUF 模型條目（1.5B / 3B / 7B）
- 擴充 `HardwareDetector`，加入 `recommend_llm()` LLM 推薦決策樹
- 思考鏈（thinking mode）在 manifest 層宣告，讓推理層（Change 17）動態處理
- `ModelManager` 新增分類查詢方法，明確分離 ASR/LLM 模型下載路徑
- settings-voice ASR 模型選單改為 manifest 驅動，允許使用者覆寫硬體建議

**Non-Goals：**

- 不實作 LLM 推理（屬 Change 17）
- 不實作 LLM 下載進度顯示 UI（屬 Change 17 設定面板）
- 不修改 `ModelManager` 下載核心機制（已完成於 Change 11）
- 不負責 thinking token 過濾邏輯（屬 Change 17）

## Decisions

### 擴充 manifest schema 加入 category 與 thinking mode 欄位

在每個模型條目新增三個欄位：
- `category`：`"asr"` 或 `"llm"`，讓 `ModelManager` 與 UI 可篩選模型類型
- `has_thinking_mode`：boolean，宣告模型是否支援思考鏈（如 Qwen3 的 `<think>` token）
- `thinking_disable_token`：string 或 null，停用思考鏈的 prompt token（如 `/no_think`）

**為何在 manifest 宣告而非硬編碼**：使未來新增 Qwen3 或其他具思考鏈模型時，只需更新 manifest，推理層（Change 17）無需修改即可正確處理。

### 採用 Qwen2.5 Instruct 系列作為預設 LLM 模型

選用 Qwen2.5-1.5B / 3B / 7B Instruct Q4_K_M GGUF：
- Qwen2.5 無思考鏈，`has_thinking_mode: false`，不需要額外過濾
- 繁體中文 / 簡體中文文字修正效果優異
- HuggingFace 官方提供完整 GGUF 分流（Bartowski 量化版）
- 保留未來擴充至 Qwen3 或其他模型的路徑（僅需在 manifest 新增條目）

### 以決策樹實作 recommend_llm() 方法

在 `HardwareDetector` 新增獨立的 `recommend_llm()` 方法，與現有 `recommend()` 方法（ASR）分開，避免邏輯耦合：

```
NVIDIA VRAM ≥ 8GB  → model="qwen2.5-7b-instruct-q4_k_m",  backend="local"
NVIDIA VRAM ≥ 4GB  → model="qwen2.5-3b-instruct-q4_k_m",  backend="local"
AMD/Intel GPU      → model="qwen2.5-1.5b-instruct-q4_k_m", backend="local"
CPU + RAM ≥ 8GB    → model="qwen2.5-1.5b-instruct-q4_k_m", backend="local"  # 警告：接近 3s 逾時
CPU + RAM < 8GB    → model=None, backend="disabled"
```

**為何低階 CPU 建議 disabled 而非 API**：`disabled` 是最安全的預設值，不強迫使用者設定 API 金鑰。使用者可在設定中手動切換至 API 模式。

### ModelManager 分類查詢方法分離 ASR 與 LLM 模型

在 `ModelManager` 新增 `list_models_by_category(category: str) -> list[dict]` 方法：
- 從已載入的 manifest 中篩選 `category` 欄位符合的條目
- ASR 設定頁面呼叫 `list_models_by_category("asr")`，LLM 設定頁面呼叫 `list_models_by_category("llm")`
- 下載邏輯不變，沿用 Change 11 的 `ModelManager.download()` 方法

**為何需要明確分離**：Change 11 當初設計為通用下載器，未區分類型。隨著同時管理 ASR 與 LLM 模型，若沒有分類查詢方法，UI 層需自行過濾，造成重複邏輯。

### 使用者模型覆寫儲存於 config，預設值來自 recommend()

硬體推薦為首次啟動的預設值，使用者選擇後寫入 `config.json`：
- `asr.selected_model`：字串，如 `"qwen3-asr-0.6b-openvino"`；`null` 表示跟隨建議
- `llm.selected_model`：字串，如 `"qwen2.5-3b-instruct-q4_k_m"`；`null` 表示跟隨建議

settings-voice 頁面：從 manifest 動態載入所有 `category="asr"` 模型，在硬體建議項目旁標示「（建議）」，選擇後寫入 config。

**為何允許覆寫**：不同使用者有不同品質/速度偏好，且部分使用者可能自行準備特定模型。Config 作為覆寫層，不干擾硬體偵測邏輯。

## Risks / Trade-offs

- [風險] Qwen2.5-1.5B 在 CPU-only + RAM 8GB 邊緣系統可能接近 Change 17 的 3 秒逾時 → 緩解措施：`recommend_llm()` 回傳時附帶 `warning="approaching_timeout_cpu"` 警示，讓 Change 17 設定面板顯示提示
- [取捨] GGUF 模型 URL 採用 Bartowski 量化版（HuggingFace bartowski/...），非 Qwen 官方帳號 → 原因：官方尚未提供 Q4_K_M 分流；未來如官方發布，只需更新 manifest URL
