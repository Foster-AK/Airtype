## 1. ModelManager 擴充

- [x] [P] 1.1 在 `airtype/utils/model_manager.py` 新增 `delete_model(model_id: str) -> bool` 方法，實作「Delete Downloaded Model」需求：刪除已下載模型檔案，回傳 True/False，未知 model_id 拋出 KeyError
- [x] [P] 1.2 在 `airtype/utils/model_manager.py` 新增 `get_model_path(model_id: str) -> Optional[str]` 方法，實作「Get Model File Path」需求：回傳已下載模型的絕對路徑，未下載或未知 ID 回傳 None
- [x] [P] 1.3 在 `tests/test_model_manager.py` 新增 `delete_model` 測試（刪除存在檔案、刪除不存在檔案、未知 model_id KeyError）
- [x] [P] 1.4 在 `tests/test_model_manager.py` 新增 `get_model_path` 測試（已下載回傳路徑、未下載回傳 None、未知 ID 回傳 None）

## 2. i18n 翻譯擴充

- [x] [P] 2.1 在 `locales/zh_TW.json` 新增 `settings.nav.models`、`settings.models.*`、`settings.voice.no_downloaded_models`、`settings.voice.no_model_hint`、`settings.llm.local_model`、`settings.llm.local_model_custom`、`settings.llm.no_downloaded_models` 等翻譯 key
- [x] [P] 2.2 在 `locales/zh_CN.json` 新增對應簡體中文翻譯
- [x] [P] 2.3 在 `locales/en.json` 新增對應英文翻譯
- [x] [P] 2.4 在 `locales/ja.json` 新增對應日文翻譯

## 3. 模型管理頁面核心 UI

- [x] 3.1 建立 `airtype/ui/settings_models.py`，依「模型卡片 UI 結構」設計決策實作 `_format_size()` 工具函式與「Model Card Display」需求：ModelCardWidget（QFrame）顯示模型名稱、描述、人類可讀檔案大小
- [x] 3.2 實作 ModelCardWidget 的「Recommended badge displayed」需求：硬體推薦模型旁顯示推薦徽章（綠底白字圓角標籤），非推薦模型不顯示
- [x] 3.3 實作 ModelCardWidget 的「Model Card Download State」需求：三種互斥狀態（未下載/下載中/已下載）以 setVisible() 切換，含下載按鈕、進度條+取消按鈕、綠勾+刪除按鈕
- [x] 3.4 實作「Model Management Settings Page」需求與「分類切換機制」設計決策：SettingsModelsPage 含 QTabBar（ASR/LLM 分類切換）+ QScrollArea 卡片列表，切換 tab 時清空並重建對應類別卡片
- [x] 3.5 實作「Theme-Aware Card Styling」需求與「卡片主題適配」設計決策：卡片 QSS 區分淺色/深色兩套樣式，主題切換時更新所有卡片 stylesheet

## 4. 背景下載與取消

- [x] 4.1 在 `airtype/ui/settings_models.py` 依「下載執行緒設計」設計決策實作 DownloadWorker（QThread），對應「Background Model Download」需求：封裝 ModelManager.download()、發射 progress/finished/error Signal、同時間最多一個下載任務（其餘卡片下載按鈕 disable）
- [x] 4.2 實作「Cancel Download」需求：_cancelled flag + progress callback 中拋出例外中斷下載迴圈

## 5. 模型刪除

- [x] 5.1 實作「Delete Downloaded Model」（UI 層）需求：點擊刪除按鈕彈出 QMessageBox 確認對話框，確認後呼叫 ModelManager.delete_model()，卡片切回未下載狀態
- [x] 5.2 實作刪除正在使用的模型警告：刪除前檢查 config.voice.asr_model 和 config.llm.local_model 是否匹配

## 6. 設定視窗整合

- [x] 6.1 修改 `airtype/ui/settings_window.py`，實作「Model Management Navigation Item」需求與「模型管理頁面分頁位置」設計決策：新增 PAGE_MODELS=2，後續索引遞增，_NAV_I18N_KEYS 插入 settings.nav.models，_add_pages() 加入 SettingsModelsPage
- [x] 6.2 實作「Cross-Page Refresh on Model State Change」需求與「跨頁面刷新 Signal」設計決策：連接 model_downloaded/model_deleted Signal 至 _on_model_state_changed()，呼叫語音頁 refresh_asr_combo() 和 LLM 頁 refresh_llm_combo()

## 7. 語音設定頁簡化

- [x] 7.1 修改 `airtype/ui/settings_voice.py` 的 _populate_asr_combo()，實作修改後的「Manifest-Driven ASR Model List」需求：只列出已下載模型、移除下載指示符 ↓、保留硬體建議標記
- [x] 7.2 新增無模型提示：無已下載模型時 dropdown 顯示 placeholder 並 disable，顯示提示 label 引導至模型管理頁面
- [x] 7.3 _on_asr_changed 增加 itemData(index) is not None 安全檢查

## 8. LLM 設定頁改造

- [x] 8.1 修改 `airtype/ui/settings_llm.py`，實作「LLM 本機模型下拉 + 自訂路徑」設計決策：將 QLineEdit 改為 QComboBox，列出 manifest 已下載 LLM 模型 + 「自訂路徑…」選項，選擇自訂路徑時顯示 QLineEdit
- [x] 8.2 實作向後相容邏輯：config.llm.local_model 不匹配任何 manifest model_id 時自動選中「自訂路徑」並填入路徑值
- [x] 8.3 新增 refresh_llm_combo() 公開方法，供模型下載/刪除後外部呼叫刷新
- [x] 8.4 更新 retranslate_ui() 以包含新增的 combo 和 label 欄位翻譯

## 9. 測試

- [x] 9.1 建立 `tests/test_settings_models.py`：測試 SettingsModelsPage 建立、QTabBar 兩個 tab、預設 ASR tab
- [x] 9.2 測試 ModelCardWidget 顯示（名稱、描述、大小）、推薦徽章顯示/隱藏
- [x] 9.3 測試 _format_size() 單元測試（MB/GB 格式化）
- [x] 9.4 測試 ModelCardWidget 三種狀態切換（未下載/下載中/已下載）
- [x] 9.5 測試 DownloadWorker（mock ModelManager.download）：progress/finished/error Signal 發射
- [x] 9.6 測試刪除流程：確認對話框觸發、刪除成功後卡片狀態切換
- [x] [P] 9.7 更新 `tests/test_settings_window.py`：分頁數量 7→8、PAGE_MODELS 索引測試、導覽至模型管理頁面
- [x] [P] 9.8 更新語音設定頁測試：驗證 dropdown 只列已下載模型、無模型時顯示 placeholder

## 10. 驗證

- [x] 10.1 執行 `pytest tests/` 確認全部測試通過
- [x] 10.2 手動啟動應用程式，驗證模型管理頁面 ASR/LLM tab 切換、卡片顯示、深色/淺色主題樣式正確
