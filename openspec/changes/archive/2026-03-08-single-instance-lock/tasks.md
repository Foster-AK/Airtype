## 1. 核心實作：檔案鎖機制（File Lock）

- [x] [P] 1.1 在 `airtype/__main__.py` 新增 `_acquire_instance_lock()` 函式，實作跨平台檔案鎖機制（`fcntl.flock` / `msvcrt.locking`），鎖檔案位置為 `~/.airtype/airtype.lock`，支援 Lock Directory Auto-Creation（`~/.airtype/` 自動建立）。回傳檔案物件（成功）或 `None`（失敗）以滿足 Test Isolation for Instance Lock 需求
  - 測試標準：函式可獨立呼叫，成功時回傳非 None 的檔案物件，失敗時回傳 None

- [x] 1.2 在 `main()` 中整合 Single Instance Enforcement：於 `setup_logging("INFO")` 之後、`AirtypeConfig.load()` 之前呼叫 `_acquire_instance_lock()`，符合 Lock Timing in Startup Sequence。鎖失敗時的行為為 `logger.warning()` + `sys.exit(0)` 優雅退出；正常關閉時在 cleanup 區段呼叫 `instance_lock.close()` 釋放鎖
  - 測試標準：`main()` 啟動時取得鎖，關閉時釋放鎖；第二次呼叫 `_acquire_instance_lock()` 回傳 None

## 2. 測試更新

- [x] [P] 2.1 依據測試策略更新 `tests/test_main.py`：在所有呼叫 `main()` 的 patch 區塊中加入 `patch("airtype.__main__._acquire_instance_lock", return_value=MagicMock())`，確保 Existing main() tests remain unaffected（Test Isolation for Instance Lock）
  - 測試標準：`pytest tests/test_main.py -v` 全部 7 個既有測試通過

- [x] [P] 2.2 新增 `tests/test_single_instance.py`：測試 Single Instance Enforcement 的四個場景——首次啟動成功取得鎖、第二個實例被拒絕、正常關閉後鎖釋放、crash 後鎖自動釋放（使用 `tempfile.mkdtemp` 隔離測試目錄）
  - 測試標準：`pytest tests/test_single_instance.py -v` 全部測試通過

## 3. 驗證

- [x] 3.1 執行完整測試套件 `pytest tests/ -v` 確認無 regression，驗證鎖的取得時機（Lock Timing in Startup Sequence）不影響既有元件初始化流程
  - 測試標準：全部測試通過，無新增失敗
