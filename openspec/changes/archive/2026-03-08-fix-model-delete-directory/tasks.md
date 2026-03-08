## 1. 核心實作：使用 shutil.rmtree 刪除目錄型模型

- [x] 1.1 [P] 修改 `airtype/utils/model_manager.py` 的 `delete_model()` 方法：使用 is_file() 替代 exists() 判斷檔案類型，同時嘗試刪除檔案和目錄——對 `.zip` 類型 filename 額外以 `shutil.rmtree()` 刪除去掉 `.zip` 後綴的目錄（Delete Downloaded Model）

## 2. 測試

- [x] 2.1 [P] 在 `tests/test_model_manager.py` 新增測試案例：驗證目錄型模型可被正確刪除（Delete Downloaded Model — Delete existing model directory）
- [x] 2.2 [P] 在 `tests/test_model_manager.py` 新增測試案例：驗證同時存在 `.zip` 檔案和目錄時兩者皆被刪除（Delete Downloaded Model — Delete model with both zip file and extracted directory）
- [x] 2.3 執行 `pytest tests/test_model_manager.py -v` 確認所有既有與新增測試通過
