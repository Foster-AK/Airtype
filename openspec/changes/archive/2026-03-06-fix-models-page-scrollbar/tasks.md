## 1. 禁用水平捲軸

- [x] [P] 1.1 在 `SettingsModelsPage._build_ui()` 中對 QScrollArea 設定 `setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)`，實現 Model Management Settings Page 規格中「水平捲軸停用」的要求。測試標準：啟動應用開啟模型管理頁面，確認無水平 scrollbar 出現。

## 2. 模型描述拆為雙行顯示

- [x] [P] 2.1 在 `ModelCardWidget._build_ui()` 中，以全形括號 `（` 為分割點解析 description 字串，將模型名稱與說明文字分離。實現 Model Card Display 規格中的雙行佈局要求。測試標準：含括號的描述正確拆為名稱行 + 說明行；不含括號的描述只顯示名稱行，說明行隱藏。

- [x] [P] 2.2 新增 `_desc_label`（灰色 11px QLabel），插入在 title_row 與 size_label 之間，顯示括號內的說明文字。測試標準：說明文字以灰色小字正確顯示於模型名稱下方、檔案大小上方。

## 3. 縮減動作區與按鈕寬度

- [x] [P] 3.1 將 `ModelCardWidget._build_ui()` 中 `action_widget` 的 `setFixedWidth` 從 130 改為 90，實現 Model Card Download State 規格中「動作區寬度 90px」的要求。測試標準：動作區寬度縮減，卡片整體不超出 ScrollArea 寬度。

- [x] [P] 3.2 將下載按鈕、進度條、取消按鈕、刪除按鈕的 `setFixedWidth` 從 120 改為 80，實現 Model Card Download State 規格中「按鈕寬度 80px」的要求。測試標準：按鈕文字完整顯示，留白適中，無截斷。

## 4. 整合驗證

- [x] 4.1 啟動應用，開啟設定 → 模型管理，切換 ASR / LLM tab，確認所有卡片正確顯示雙行佈局、無水平 scrollbar、按鈕操作正常。測試標準：深色/淺色主題下均無水平捲軸，所有模型卡片資訊完整可見。
