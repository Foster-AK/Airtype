## Context

`ModelManager._download_hf_repo()` 使用 `huggingface_hub.snapshot_download()` 下載多檔案 HF repo 模型
（如 OpenVINO IR）。為了將逐檔下載進度彙總成單一 callback，程式使用 `functools.partial(_HfProgressAdapter, shared=shared)`
作為 `tqdm_class` 參數傳入 `snapshot_download()`。

`huggingface_hub` 內部透過 `tqdm.contrib.concurrent.thread_map` 使用此 `tqdm_class`，
該函式對 class 有完整的 protocol 要求（`get_lock`、`set_lock`、positional iterable 建構、`__iter__`），
`functools.partial` 不滿足這些要求，導致封裝後下載全部失敗。

## Goals / Non-Goals

**Goals:**

- 讓 `_HfProgressAdapter` 實作完整的 tqdm class protocol，相容 `thread_map`
- 保持 `_SharedProgress` 彙總進度機制不變
- 確保單檔直連下載路徑（`_download_url` via httpx.stream）不受影響
- 強化測試以模擬真實 `thread_map` 行為，防止日後回歸

**Non-Goals:**

- 不重寫整個下載管線
- 不修改 `_download_url`（httpx 直連路徑）
- 不新增功能或改變對外 API

## Decisions

### 補齊 _HfProgressAdapter 的 tqdm class protocol

`_HfProgressAdapter` 需補齊以下方法以相容 `tqdm.contrib.concurrent.thread_map`：

| 方法 | 用途 | 實作方式 |
|------|------|---------|
| `get_lock()` classmethod | `thread_map` 取得 threading lock | 回傳 `threading.Lock()` 實例，快取於 `cls._lock` |
| `set_lock(lock)` classmethod | `thread_map` 設定 lock 到 class 屬性 | 設定 `cls._lock = lock` |
| `__init__(iterable=None, *, ...)` | `thread_map` 以 positional iterable 實例化 | 接受 optional positional `iterable` 參數 |
| `__iter__` | `list(tqdm_instance)` 迭代結果 | yield from iterable，每個 item 呼叫 `update(1)` |

**替代方案**：完全不用 `tqdm_class`，改用 `snapshot_download` 的其他 hook。
但 `huggingface_hub` 目前沒有其他進度 hook，`tqdm_class` 是唯一方式。

### 以動態子類別取代 functools.partial

`_download_hf_repo` 中使用動態子類別 `_BoundAdapter` 綁定 `shared` 參數：

```python
class _BoundAdapter(_HfProgressAdapter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("shared", shared)
        super().__init__(*args, **kwargs)
```

**理由**：子類別正確繼承 `get_lock`、`set_lock` 等 classmethod，
而 `functools.partial` 不是 class，無法作為 `ThreadPoolExecutor` 的 initializer。

### shared 參數改為 Optional

`thread_map` 的 `ThreadPoolExecutor` 使用 `tqdm_class.set_lock` 作為 worker initializer，
不會傳入 `shared`。因此 `_HfProgressAdapter.__init__` 的 `shared` 須改為 `Optional[_SharedProgress] = None`，
`update()` 等方法加入 `if self._shared:` guard。

## Risks / Trade-offs

- **[風險] huggingface_hub 未來版本可能新增更多 tqdm 方法呼叫** → 緩解：已實作完整的最小 tqdm protocol（get_lock / set_lock / __init__ / __iter__ / update / close / context manager / set_description / set_postfix），覆蓋了 thread_map 的所有需求。測試模擬真實 thread_map 行為以防回歸。
- **[風險] 動態子類別在每次 _download_hf_repo 呼叫時建立** → 影響極小，下載操作本身就是低頻重量操作。
