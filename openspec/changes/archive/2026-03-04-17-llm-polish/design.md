## 背景

LLM 潤飾是選用性後處理，可提升 ASR 輸出品質。PRD §6.4 定義處理管線，§5.4 定義設定 UI。

相依性：13-core-controller、16-settings-panel。

## 目標 / 非目標

**目標：**

- 透過 llama-cpp-python 搭配 GGUF 模型實作本機 LLM
- API 整合（OpenAI 相容端點）
- 三種潤飾模式（輕度 / 中度 / 完整）
- 比對原始與潤飾結果的預覽 UI
- 3 秒逾時並回退至原始文字

**非目標：**

- 不負責模型下載（由 11-model-hardware-mgr 處理）
- 不負責辭典處理（由 18-dictionary 處理）

## 決策

### 以 llama-cpp-python 進行本機 LLM 推理

使用 `llama_cpp.Llama` 類別搭配 GGUF 模型。Context 長度 2048 tokens，最大生成長度 = 輸入長度 × 1.5。

### 透過 httpx 呼叫 OpenAI 相容 API

所有 API 提供者（Anthropic、OpenAI、Ollama、自訂）均使用 OpenAI chat completions 格式。使用單一 `httpx.AsyncClient`，支援可設定的 base_url 與 API 金鑰。

### 以提示詞模板變體實作潤飾模式

三種提示詞模板：輕度（僅標點）、中度（+ 流暢度）、完整（+ 文法）。模板儲存於程式碼中，使用者可透過 config `llm.custom_prompt` 覆寫。

### Qwen2.5 直接呼叫 create_chat_completion（無需手動組裝 ChatML）

Qwen2.5-Instruct 系列透過 `create_chat_completion()` 直接傳入 messages 串列即可，不需手動組裝 ChatML prompt，也不需要 `strip_thinking` 後處理（Qwen2.5 不具備 thinking mode）。相較 Qwen3 版本大幅簡化。

### 提示詞採 Few-shot 範例設計

小模型（0.5B / 1.5B）instruction following 能力弱，但 pattern matching（模式模仿）能力強。每個模式的 system prompt 均包含一組完整 input→output 範例，讓模型直接模仿輸出格式，比單純列條列規則更有效。提示詞控制在約 180 字以內（含範例），避免注意力被稀釋、遺漏「不要加說明」的指令。末尾統一放置「直接輸出結果，不要加任何說明。」，使其離生成起點最近。

內建 prompt 為預設值；使用者透過 config `llm.custom_prompt` 設定後，自訂 prompt 取代所有模式的內建 prompt，此優先級不因 few-shot 更新而改變。

### 根據模型大小自動降級潤飾模式

`model_size_b` 參數由使用者/設定檔提供，引擎依此判斷最高可用模式：

| 模式 | 最低模型大小 |
|------|------------|
| LIGHT | 0B（所有模型） |
| MEDIUM | 1.5B |
| FULL | 3.0B |

若請求的模式超出模型能力（例如以 1.5B 模型請求 FULL），引擎自動降至最高可用模式，並以 INFO 等級記錄降級事件（`logger.info("mode downgraded: %s → %s", requested, actual)`）。`PolishEngine.polish()` 仍回傳 `str`，不需包裝為結構化物件。

### ASR 輸出前處理（pre_clean）與 LLM 輸出後處理（post_clean）

**pre_clean**（在呼叫 LLM 之前）：
- 壓縮連續語氣詞（嗯嗯嗯 → 嗯）
- 壓縮重複贅詞（然後然後 → 然後）
- 移除多餘空白字元

**post_clean**（在取得 LLM 輸出之後）：
- 移除小模型常見廢話前綴（「好的，」「以下是...：」「輸出：」等）
- 移除 markdown 程式碼區塊包裹
- 移除首尾引號包裹（半形 `"..."` 或全形 `「...」`）

### 採樣參數（Sampling Parameters）

本機推理採用固定採樣參數以確保確定性輸出：`temperature=0.1`、`top_p=0.8`、`top_k=20`、`min_p=0.0`、`repeat_penalty=1.1`。Context window 設定為 `n_ctx=4096`（較原先 2048 上調，以支援較長段落的完整編輯）。

## 風險 / 取捨

- [風險] 本機 LLM 在 CPU 上可能過慢 → 緩解措施：3 秒逾時；建議改用 GPU 或 API 模式
- [取捨] API 模式會將文字傳送至雲端 → 使用者須明確選擇啟用；預設為關閉
- [取捨] n_ctx=4096 比 2048 消耗更多記憶體 → 對 1.5B 模型影響有限（GGUF Q4_K_M ~1GB），可接受
