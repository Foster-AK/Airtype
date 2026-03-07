## ADDED Requirements

### Requirement: HuggingFace Repo Download tqdm Protocol Compliance

The `_HfProgressAdapter` class used as `tqdm_class` for `huggingface_hub.snapshot_download()` SHALL implement the full tqdm class protocol required by `tqdm.contrib.concurrent.thread_map`. The class SHALL provide `get_lock()` and `set_lock(lock)` class methods, accept an optional positional iterable in `__init__`, and support iteration via `__iter__`.

#### Scenario: thread_map calls get_lock on tqdm_class

- **WHEN** `huggingface_hub.snapshot_download()` internally calls `tqdm_class.get_lock()`
- **THEN** the class method SHALL return a `threading.Lock` instance

#### Scenario: thread_map calls set_lock on tqdm_class

- **WHEN** `huggingface_hub.snapshot_download()` internally calls `tqdm_class.set_lock(lock)`
- **THEN** the class method SHALL store the lock for thread-safe access

#### Scenario: thread_map instantiates tqdm_class with positional iterable

- **WHEN** `thread_map` calls `tqdm_class(iterable, **kwargs)` with a positional iterable argument
- **THEN** the instance SHALL store the iterable and support iteration via `__iter__`

#### Scenario: thread_map iterates tqdm_class instance

- **WHEN** `list(tqdm_instance)` is called on an instance created with an iterable
- **THEN** the instance SHALL yield all items from the iterable

#### Scenario: Progress adapter shared parameter is optional

- **WHEN** `_HfProgressAdapter` is instantiated without a `shared` parameter (e.g., by `ThreadPoolExecutor` initializer)
- **THEN** the instance SHALL NOT raise an error and `update()` calls SHALL be silently ignored
