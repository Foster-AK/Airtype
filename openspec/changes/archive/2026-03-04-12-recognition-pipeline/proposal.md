## 為什麼

這是將音訊擷取 → VAD → ASR → 文字注入串連為端對端辨識管線的整合層。需要批次（錄完再辨識）和串流（即時部分結果）兩種模式。

參考：PRD §8.2（音訊資料流）、§4.2（互動流程）。

相依性：03-vad-engine、05-text-injector、06-asr-abstraction、08-asr-qwen-openvino。

## 變更內容

- 實作批次辨識管線：VAD 分段音訊 → ASR 辨識 → 注入文字
- 實作串流辨識管線：音訊區塊 → 串流 ASR → 部分結果 → 最終文字
- 將 VAD 狀態機事件連接至 ASR 觸發
- 管理音訊緩衝區從擷取到 ASR 的交接

## 功能

### 新增功能

- `recognition-pipeline`：端對端批次與串流語音辨識管線

### 修改功能

（無）

## 影響

- 新增檔案：`airtype/core/pipeline.py`、`tests/test_pipeline.py`
- 相依於：03-vad-engine、05-text-injector、06-asr-abstraction、08-asr-qwen-openvino
