## Problem

封裝後的 Airtype 在下載 HuggingFace 模型時報錯：
`'functools.partial' object has no attribute 'get_lock'`。

`ModelManager._download_hf_repo()` 使用 `functools.partial(_HfProgressAdapter, shared=shared)` 作為
`snapshot_download()` 的 `tqdm_class` 參數。但 `huggingface_hub` 內部透過 `tqdm.contrib.concurrent.thread_map`
使用 `tqdm_class`，該函式對 `tqdm_class` 有完整的 class-level protocol 要求（`get_lock`、`set_lock`、
接受 positional iterable、`__iter__`），而 `functools.partial` 不是真正的 class，導致下載失敗。

## Root Cause

`thread_map`（`tqdm.contrib.concurrent`）的呼叫流程：

1. `tqdm_class.get_lock()` — 取得 class-level threading lock
2. `tqdm_class.set_lock(lock)` — 設定 lock 到 class 屬性
3. `ThreadPoolExecutor(initializer=tqdm_class.set_lock, initargs=(lock,))` — worker 初始化
4. `tqdm_class(iterable, **kwargs)` — 以 positional iterable 實例化
5. `list(instance)` — 迭代實例取得結果

`functools.partial` 物件：
- 沒有 `get_lock` 屬性 → 步驟 1 直接 `AttributeError`
- 沒有 `set_lock` 屬性 → 即使繞過步驟 1 也會在步驟 2 失敗
- 不是真正的 class → 無法作為 `ThreadPoolExecutor` 的 `initializer` 參數

此外，`_HfProgressAdapter.__init__` 使用 `*`（keyword-only），不接受 positional iterable；
且缺少 `__iter__` 方法，`list(instance)` 會 `TypeError`。

## Proposed Solution

將 `_HfProgressAdapter` 補齊完整的 tqdm class protocol：

1. **加入 `set_lock(cls, lock)` classmethod** — `thread_map` 的 `ensure_lock` 必要
2. **`__init__` 接受 positional `iterable` 參數** — `thread_map` 以 `tqdm_class(iterable, **kwargs)` 實例化
3. **加入 `__iter__` 方法** — `list(tqdm_instance)` 迭代必要
4. **`shared` 改為 `Optional`** — `set_lock` initializer 會以無 `shared` 的方式建立實例
5. **`update()` 加 `shared` guard** — `shared=None` 時不 crash
6. **以動態子類別取代 `functools.partial`** — 正確繼承所有 class methods

## Success Criteria

- `snapshot_download` 搭配自訂 `tqdm_class` 可正常下載 HF repo 模型（多檔案）
- 進度 callback 正確回報彙總進度（百分比遞增至 100%）
- 單檔直連下載（httpx.stream 路徑）不受影響
- 測試模擬真實 `thread_map` 行為（`get_lock`、`set_lock`、positional iterable、`__iter__`）
- 無 `progress_callback` 時不注入 `tqdm_class`

## Impact

- 受影響程式碼：`airtype/utils/model_manager.py`（`_HfProgressAdapter` 類別 + `_download_hf_repo` 方法）
- 受影響測試：`tests/test_model_manager_hf_progress.py`（強化測試覆蓋）
- 相關 spec：`model-download`（不需修改需求，僅修正實作）
