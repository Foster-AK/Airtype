## Context

專案有兩個同性質的「名稱解析」缺陷：

1. **ASR**：`ASREngineRegistry.load_default_engine()` 直接使用 `config.voice.asr_model`（模型名稱 `"qwen3-asr-0.6b"`）呼叫 `set_active_engine()`，但註冊表 key 是引擎 ID（`"qwen3-vulkan"` 等），`KeyError` → `asr_engine=None` → 管線未建立。`voice.asr_inference_backend` 也未被使用。

2. **LLM**：`PolishEngine._get_local_engine()` 將 `llm.local_model`（模型 ID `"qwen2.5-1.5b-instruct-q4_k_m"`）直接傳給 `Llama(model_path=...)`，但實際檔案是 `~/.airtype/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`。首次推理時找不到檔案 → `PolishError` → 靜默回退。

兩者都可透過 `models/manifest.json` 進行名稱到實體的解析。

## Goals / Non-Goals

**Goals:**

- 讓 `load_default_engine()` 從模型名稱 + 推理後端偏好正確解析出引擎 ID
- 讓 `_get_local_engine()` 從模型 ID 正確解析出 GGUF 檔案路徑
- 向下相容：若使用者直接填寫引擎 ID 或完整路徑仍可運作

**Non-Goals:**

- 不修改各 ASR 引擎的 `register()` 函式或 ENGINE_ID 命名
- 不修改 config schema
- 不新增 UI 元件或錯誤提示彈窗

## Decisions

### ASR 模型名稱到引擎 ID 映射表

在 `asr_engine.py` 模組層級新增 `_MODEL_ENGINE_MAP` 字典，結構為 `dict[str, list[str]]`：key 為模型名稱，value 為按優先順序排列的引擎 ID 清單。

選擇 list 而非 dict[backend→engine_id] 是因為 `"auto"` 模式只需遍歷已登錄的引擎，不需按 backend 名稱精確匹配。

```python
_MODEL_ENGINE_MAP: dict[str, list[str]] = {
    "qwen3-asr-0.6b": ["qwen3-openvino", "qwen3-pytorch-cuda", "qwen3-vulkan"],
    "breeze-asr-25": ["breeze-asr-25"],
    "sherpa-sensevoice": ["sherpa-sensevoice"],
    "sherpa-paraformer": ["sherpa-paraformer"],
}
```

### load_default_engine 解析策略

修改 `load_default_engine(self, config)` 的邏輯為：

1. 讀取 `model_id = config.voice.asr_model` 和 `backend = config.voice.asr_inference_backend`
2. **直接匹配**：若 `model_id` 存在於 `self._factories`，視為引擎 ID 直接使用
3. **映射解析**：若 `model_id` 存在於 `_MODEL_ENGINE_MAP`，取得候選引擎清單
   - `backend == "auto"`：遍歷候選清單，選第一個已登錄的引擎
   - `backend` 為特定值：在候選清單中篩選包含 backend 關鍵字的引擎 ID
4. **失敗**：記錄 WARNING 並保持無作用中引擎

### 後端關鍵字匹配規則

backend 值與引擎 ID 的對應關係透過子字串包含判斷（`backend in engine_id`）：
- `"openvino"` → 匹配 `"qwen3-openvino"`
- `"pytorch-cuda"` 或 `"cuda"` → 匹配 `"qwen3-pytorch-cuda"`
- `"vulkan"` → 匹配 `"qwen3-vulkan"`

### LLM 模型 ID 到檔案路徑解析

在 `PolishEngine._get_local_engine()` 中，將 `llm.local_model`（模型 ID）解析為實際檔案路徑：

1. 若 `local_model` 已是有效檔案路徑（`Path(local_model).exists()`），直接使用（向下相容）
2. 否則讀取 `models/manifest.json`，在 `models` 陣列中找到 `id == local_model` 的條目
3. 取得其 `filename` 欄位，組合成 `~/.airtype/models/{filename}` 完整路徑
4. 找不到時拋出 `PolishError` 附帶清楚的錯誤訊息

選擇在 `_get_local_engine()` 解析而非在 config 層解析，是因為 config 應保持宣告式（存模型 ID，非路徑），路徑組裝屬於引擎初始化的職責。

## Risks / Trade-offs

- **[風險] ASR 映射表硬編碼** → 新增 ASR 引擎時需同步更新 `_MODEL_ENGINE_MAP`。緩解：在映射表旁加入註解提醒。
- **[風險] ASR 子字串匹配可能誤判** → 若未來引擎 ID 命名碰撞可能匹配錯誤。緩解：目前引擎 ID 命名清晰，list 順序提供優先順序保障。
- **[風險] LLM manifest 讀取失敗** → manifest 損壞或被刪除時無法解析路徑。緩解：拋出 `PolishError` 帶清楚訊息，`PolishEngine.polish()` 已有回退機制。
