## 背景

辨識管線連接音訊 → VAD → ASR → 文字注入。兩種模式：批次（較高品質）和串流（即時回饋）。

相依性：03-vad-engine、05-text-injector、06-asr-abstraction、08-asr-qwen-openvino。

## 目標 / 非目標

**目標：**

- 批次管線：VAD 偵測語音結束 → 累積音訊 → ASR → 文字注入
- 串流管線：音訊區塊 → 串流 ASR → 部分結果 → 最終結果 → 注入
- 元件間音訊緩衝區的乾淨交接

**非目標：**

- 不含 UI（屬於 14-overlay-ui）
- 不含狀態機邏輯（屬於 13-core-controller）

## 決策

### 批次管線採用循序階段

音訊在 SPEECH 狀態期間累積於緩衝區。當 SPEECH_ENDED 時，整段緩衝區送至 ASR 進行批次辨識。結果經後處理後注入文字。

### 串流管線透過 VAD 分段區塊

對於支援串流的引擎（sherpa-onnx、Qwen3-ASR with vLLM），音訊區塊持續送入。對於不支援串流的引擎（Breeze、OpenVINO），VAD 分段模擬串流，辨識短片段。

### 管線作為可組合類別

`RecognitionPipeline` 接受注入的相依元件（AudioCapture、VadEngine、ASREngine、TextInjector），以便使用模擬元件進行測試。

## 風險 / 取捨

- [風險] 串流偽模式可能出現可見的重複辨識瑕疵 → 緩解措施：僅在 is_final=True 時顯示最終文字
- [取捨] 批次模式延遲較長但準確度較高 → 由使用者透過設定選擇
