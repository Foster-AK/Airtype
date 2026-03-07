## 1. 依賴設定

- [x] [P] 1.1 將 psutil 加入正式依賴：在 `pyproject.toml` 的 `dependencies` 加入 `psutil>=5.9`（對應設計決策「將 psutil 加入正式依賴」）

## 2. RAM Detection with Reliable Fallback Chain 實作

- [x] [P] 2.1 實作 RAM Detection with Reliable Fallback Chain：在 `_get_total_ram_mb()` 於 wmic 嘗試之前插入 ctypes `kernel32.GlobalMemoryStatusEx` 備案（對應設計決策「加入 ctypes GlobalMemoryStatusEx 作為 Windows 備案」；覆蓋 Scenario: RAM Detection via ctypes on Windows）
- [x] 2.2 強化各 fallback 層的 debug log：每層失敗時以 DEBUG level 記錄具體失敗原因（對應設計決策「強化各 fallback 層的 debug log」；覆蓋 Scenario: Debug Log on Fallback Failure）
- [x] 2.3 確認 RAM Detection Fallback Warning 行為：當所有方法均失敗時，仍輸出 WARNING 並回傳 4096

## 3. 測試

- [x] [P] 3.1 撰寫單元測試：Scenario RAM Detection via psutil（mock `psutil.virtual_memory()` 回傳已知 RAM 值，驗證結果正確且無 WARNING）
- [x] [P] 3.2 撰寫單元測試：Scenario RAM Detection via ctypes on Windows（mock `ctypes.windll.kernel32.GlobalMemoryStatusEx`，驗證 ctypes fallback 回傳正確 RAM 值）
- [x] [P] 3.3 撰寫單元測試：Scenario RAM Detection Fallback Warning（mock 所有方法失敗，驗證回傳 4096 且觸發 WARNING log）
- [x] 3.4 執行 `pytest` 確認所有測試通過；重新安裝專案（`pip install -e .`）後啟動應用程式，確認不再出現 `無法取得 RAM 資訊` WARNING
