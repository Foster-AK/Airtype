# Qwen3-ASR 串流輸出與詞典功能調查報告

日期：2026-03-21

## 摘要

經過對 [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) 原始碼的深入調查，以下是關於**串流輸出**與**詞典（熱詞）功能**的完整分析。

---

## 一、串流輸出（Streaming）

### 結論：✅ 原生支援，但僅限 vLLM 後端

Qwen3-ASR **完整支援串流推理**，提供三個核心 API：

| API 方法 | 用途 |
|---|---|
| `init_streaming_state()` | 初始化串流狀態 |
| `streaming_transcribe(pcm16k, state)` | 逐步送入音訊片段進行辨識 |
| `finish_streaming_transcribe(state)` | 結束串流，處理剩餘緩衝 |

### 串流運作機制（源碼分析）

1. **Chunk-based 增量解碼**：音訊以固定大小的 chunk（預設 2 秒）累積，每當 buffer 湊滿一個 chunk 就觸發一次推理
2. **全量重送策略**：每次推理時，會將從開始到目前為止的**所有音訊**重新送給模型（`audio_accum`），而非只送新的 chunk
3. **Prefix 前綴策略**：利用前次辨識結果作為 prompt prefix，引導模型延續前文
4. **Rollback 防抖機制**：
   - 前 N 個 chunk（`unfixed_chunk_num`，預設 2-4）不使用 prefix，避免初期錯誤累積
   - 之後的 chunk 會回退最後 K 個 token（`unfixed_token_num`，預設 5），減少邊界抖動

### 串流限制

- **僅支援 vLLM 後端**（Transformers 後端不支援）
- **不支援批次推理**（一次只能處理一個音訊流）
- **不支援時間戳**（無法搭配 ForcedAligner）
- **效能考量**：由於每次都重送全量音訊，隨著音訊時間增長，每次推理的計算量會線性增加

### 串流參數

```python
state = asr.init_streaming_state(
    context="",              # 上下文字串（作為 system prompt）
    language=None,           # 可選：強制指定語言
    unfixed_chunk_num=2,     # 前 N 個 chunk 不用前綴
    unfixed_token_num=5,     # 前綴回退 token 數
    chunk_size_sec=2.0,      # 每個 chunk 的秒數
)
```

### 串流 Web Demo

官方提供 Flask 串流 Demo（`qwen_asr/cli/demo_streaming.py`），使用瀏覽器麥克風透過 WebAudio API 擷取音訊，每 500ms 送一次 chunk，即時顯示辨識結果。

---

## 二、詞典 / 熱詞功能（Dictionary / Hotwords）

### 結論：❌ 無原生支援，但有 `context` 機制可部分替代

### 原始碼確認

在整個 Qwen3-ASR 程式碼中，**完全沒有** hotword、bias、dictionary、lexicon 相關的實作。搜尋結果為零。

### Context 機制（最接近詞典的功能）

Qwen3-ASR 提供 `context` 參數，其運作方式：

```python
# context 被放入 system message
def _build_messages(self, context, audio_payload):
    return [
        {"role": "system", "content": context or ""},  # ← context 在這裡
        {"role": "user", "content": [{"type": "audio", "audio": audio_payload}]},
    ]
```

**官方範例中的用法**（來自 `examples/example_qwen3_asr_vllm.py`）：

```python
results = asr.transcribe(
    audio=[URL_ZH, zh_b64, (en_wav, en_sr)],
    context=["", "交易 停滞", ""],  # ← 提供關鍵詞作為上下文
    language=[None, "Chinese", "English"],
)
```

這表明 **context 可以用來提示模型某些特定詞彙**，但這是基於 LLM 的 prompt engineering，而非傳統 ASR 的熱詞偏置（bias）機制。

### Context 在串流模式中的支援

串流模式 **也支援 context**：

```python
state = asr.init_streaming_state(
    context="交易 停滞",  # ← 串流模式也可以設定 context
    language="Chinese",
)
```

context 會在 `_build_text_prompt()` 中被嵌入 prompt，並在整個串流過程中持續使用。

---

## 三、替代方案分析：後處理文字取代

### 方案描述

既然 Qwen3-ASR 沒有原生詞典功能，目前專案的設計是在 ASR 輸出後進行文字取代（openspec 的 dictionary-engine 設計）。

### 效能影響評估

| 面向 | 影響 | 說明 |
|---|---|---|
| **字串取代** | 極低 | 純 Python 字串操作，微秒級別 |
| **正則取代** | 低 | 預編譯後的正則匹配，規則 < 100 條時可忽略 |
| **延遲增加** | 可忽略 | 後處理在 ASR 推理之後執行，不阻塞推理本身 |
| **串流相容** | ⚠️ 需注意 | 串流模式下，每個 chunk 的結果是「暫時性」的，後處理替換可能被下一次推理覆蓋 |

### 串流模式下的後處理挑戰

1. **結果不穩定**：串流模式的前幾個 chunk 辨識結果會變動（unfixed），此時做取代可能無意義
2. **邊界問題**：一個詞可能跨兩個 chunk 的邊界，導致取代失敗
3. **重複取代**：由於串流的 rollback 機制，相同的文字可能被多次處理

**建議**：後處理取代應只在 `finish_streaming_transcribe()` 後的最終結果上執行，或在 `chunk_id >= unfixed_chunk_num` 後的穩定區段執行。

---

## 四、綜合建議

### 短期方案（推薦）

1. **利用 context 機制**：將詞典中的熱詞以空格分隔傳入 `context` 參數，利用 LLM 的上下文理解能力提升辨識精度
2. **後處理取代**：在 ASR 最終輸出後套用替換規則，效能影響可忽略
3. **串流模式**：使用 vLLM 後端的串流 API，搭配 context 注入熱詞

### Context + 後處理的整合方式

```python
# 1. 從詞典中提取熱詞，注入 context
hot_words = dictionary.get_active_hot_words()
context_str = " ".join([hw.word for hw in hot_words])

# 2. 串流辨識，帶 context
state = asr.init_streaming_state(context=context_str, language="Chinese")
# ... streaming_transcribe ...
asr.finish_streaming_transcribe(state)

# 3. 最終結果做後處理取代
final_text = state.text
for rule in dictionary.get_replace_rules():
    final_text = rule.apply(final_text)
```

### 長期方案（可選）

- **微調模型**：Qwen3-ASR 支援 SFT 微調（`finetuning/qwen3_asr_sft.py`），可針對專業領域訓練專用模型
- **Constrained Decoding**：vLLM 支援 guided decoding / logit bias，理論上可在推理時偏置特定 token 的機率，但需要自行實作與 Qwen3-ASR 的整合

---

## 五、vLLM 後端評估：不納入本專案

### 結論：❌ 不適合本專案，不需要整合

### 理由

1. **硬體門檻過高**：vLLM 僅支援 NVIDIA GPU + CUDA，且 VRAM 需求大（通常需 8GB+）。不支援 AMD、Intel GPU 及純 CPU 環境，無法涵蓋大部分桌面使用者的配備。

2. **本專案已有完整的硬體適配鏈**：`hardware-detection` spec 定義的決策樹已覆蓋所有情境——NVIDIA GPU → PyTorch CUDA、AMD/Intel GPU → Vulkan（chatllm.cpp）、CPU → OpenVINO INT8、低階 CPU → sherpa-onnx SenseVoice。不需要再加一個高門檻的後端。

3. **vLLM 的串流是「偽串流」**：每次推理都重送全量音訊（`audio_accum`），延遲隨音訊長度線性增加。相比之下 sherpa-onnx 提供真正的增量串流辨識，更適合桌面端即時輸入場景。

4. **Context 機制不需要 vLLM**：`context` 參數的注入在所有 Qwen3 引擎（PyTorch CUDA、Vulkan、ONNX）中均可實作，因為它只是 prompt 的一部分，與推理後端無關。

5. **vLLM 是伺服器端工具**：vLLM 設計用於高併發、大規模部署的伺服器端推理（多用戶、批次排程、PagedAttention），對桌面端單用戶場景是過度設計。其安裝與相依套件也偏向伺服器環境（需要特定版本的 CUDA toolkit、PyTorch 等）。

### 現有替代方案已足夠

| 需求 | 現有方案 | 狀態 |
|---|---|---|
| GPU 推理 | PyTorch CUDA / Vulkan (chatllm.cpp) | ✅ 已實作 |
| CPU 推理 | ONNX Runtime / OpenVINO | ✅ 已實作 |
| 真實串流辨識 | sherpa-onnx (SenseVoice / Paraformer) | ✅ 已實作 |
| 詞典 / 熱詞 | context 注入 + 後處理取代 | ✅ 已設計 |
| 硬體自動偵測 | HardwareDetector + 推薦決策樹 | ✅ 已實作 |

---

## 六、關鍵發現摘要

| 功能 | 支援狀態 | 備註 |
|---|---|---|
| 串流輸出 | ✅ 支援 | 僅 vLLM 後端 |
| 詞典 / 熱詞 | ❌ 無原生支援 | 可用 `context` 參數部分替代 |
| 後處理取代 | ✅ 可行 | 效能影響極低，但串流模式需注意時機 |
| 批次串流 | ❌ 不支援 | 串流模式限單一音訊流 |
| 串流 + 時間戳 | ❌ 不支援 | 串流不支援 ForcedAligner |
| 微調 | ✅ 支援 | 可作為長期方案 |
