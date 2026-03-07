## 1. 補齊 _HfProgressAdapter 的 tqdm class protocol

- [x] [P] 1.1 在 `_HfProgressAdapter` 加入 `_lock` class attribute（初始值 `None`），並實作 `get_lock()` classmethod（回傳 `threading.Lock`，快取於 `cls._lock`）。驗證：`_HfProgressAdapter.get_lock()` 回傳 Lock 實例且多次呼叫回傳同一物件。
- [x] [P] 1.2 在 `_HfProgressAdapter` 加入 `set_lock(cls, lock)` classmethod（設定 `cls._lock = lock`）。驗證：呼叫後 `cls._lock` 等於傳入的 lock 物件。
- [x] 1.3 修改 `_HfProgressAdapter.__init__` 接受 optional positional `iterable` 參數（`iterable=None`），並依 design「shared 參數改為 Optional」決策將 `shared` 改為 `Optional[_SharedProgress] = None`。驗證：`_HfProgressAdapter(iter([1,2,3]), total=3)` 不報錯。
- [x] 1.4 在 `_HfProgressAdapter` 加入 `__iter__` 方法，yield iterable 中每個 item 並呼叫 `update(1)`。驗證：`list(_HfProgressAdapter(iter([1,2,3]), shared=shared, total=3))` 回傳 `[1,2,3]`。
- [x] 1.5 在 `update()` 方法加入 `if self._shared:` guard，shared 為 None 時靜默忽略。驗證：`_HfProgressAdapter(total=10).update(5)` 不報錯。

## 2. 以動態子類別取代 functools.partial

- [x] 2.1 修改 `_download_hf_repo` 方法，以動態子類別 `_BoundAdapter` 取代 `functools.partial`，在 `__init__` 中透過 `kwargs.setdefault("shared", shared)` 綁定 shared 參數。驗證：`_BoundAdapter` 繼承 `get_lock`、`set_lock` 等 classmethod。
- [x] 2.2 移除 `import functools`（已無使用處）。驗證：檔案中無 `functools` 引用。

## 3. 強化測試模擬真實 thread_map 行為

- [x] 3.1 在 `test_model_manager_hf_progress.py` 的 `TestSharedProgressAndAdapter` 新增測試：驗證 `get_lock()` 和 `set_lock()` 的 class-level protocol（HuggingFace Repo Download tqdm Protocol Compliance）。驗證：測試通過。
- [x] 3.2 在 `TestSharedProgressAndAdapter` 新增測試：驗證 `__init__` 接受 positional iterable 且 `__iter__` 正確迭代（thread_map instantiates tqdm_class with positional iterable）。驗證：測試通過。
- [x] 3.3 在 `TestSharedProgressAndAdapter` 新增測試：驗證 shared 參數為 Optional（Progress adapter shared parameter is optional），`update()` 在無 shared 時不報錯。驗證：測試通過。
- [x] 3.4 更新 `TestDownloadHfRepoProgress.test_injects_tqdm_class_with_callback` 中的 `fake_snapshot_download`，加入 `get_lock()`/`set_lock()` 呼叫與 positional iterable 實例化，模擬真實 `thread_map` 行為。驗證：測試通過。

## 4. 驗證

- [x] 4.1 執行 `python -m pytest tests/test_model_manager_hf_progress.py -v`，確認所有測試通過。
- [x] 4.2 執行 `python -m pytest tests/test_model_manager.py -v`，確認單檔直連下載路徑不受影響。
