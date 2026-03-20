# ASR Abstraction Spec

## Requirement: ASR Engine Protocol

The system SHALL define an `ASREngine` Protocol with the following methods: `load_model(model_path, config)`, `recognize(audio) -> ASRResult`, `recognize_stream(chunk) -> PartialResult`, `set_hot_words(words)`, `set_context(context_text)`, `get_supported_languages() -> list[str]`, and `unload()`. All ASR engine implementations SHALL conform to this Protocol.

### Scenario: Mock Engine Conforms to Protocol

- **WHEN** a mock engine class implements all Protocol methods
- **THEN** the type system SHALL accept it as a valid ASREngine

### Scenario: Engine Missing a Method

- **WHEN** a class is missing the `recognize` method
- **THEN** it SHALL NOT satisfy the ASREngine Protocol

## Requirement: ASR Result Data Model

Recognition results SHALL be returned as an `ASRResult` dataclass containing: `text` (str), `language` (str), `confidence` (float, 0.0–1.0), and `segments` (list of text segments with timestamps). Streaming partial results SHALL use a `PartialResult` dataclass containing: `text` (str) and `is_final` (bool).

### Scenario: Full Recognition Result

- **WHEN** an engine completes batch recognition
- **THEN** the result SHALL contain text, language code, confidence score, and a list of segments

### Scenario: Streaming Partial Result

- **WHEN** an engine produces a streaming partial result
- **THEN** the result SHALL contain the partial text and an is_final flag

## Requirement: Engine Registry

The system SHALL maintain an `ASREngineRegistry` that maps string engine IDs to factory callables. Engines SHALL be registered via `register_engine(id, factory)`. `get_engine(id)` SHALL return a new engine instance.

### Scenario: Register and Retrieve Engine

- **WHEN** an engine factory is registered with the ID "mock-engine"
- **THEN** `get_engine("mock-engine")` SHALL return a valid engine instance

### Scenario: Retrieve Unregistered Engine

- **WHEN** `get_engine("nonexistent")` is called
- **THEN** the system SHALL raise a `KeyError`

## Requirement: Runtime Engine Switching

The system SHALL support switching the active ASR engine at runtime via `set_active_engine(id)`. The switch SHALL unload the current engine before loading the new one.

### Scenario: Switch Active Engine

- **WHEN** `set_active_engine("engine-b")` is called while engine-a is active
- **THEN** engine-a SHALL be unloaded and engine-b SHALL become the active engine

## Requirement: Load Default Engine from Configuration

At startup, the system SHALL load the ASR engine specified by the `voice.asr_model` configuration setting. If the specified engine is not registered, the system SHALL log a warning and remain with no active engine.

### Scenario: Configuration Specifies a Valid Engine

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and that engine is registered
- **THEN** the system SHALL load it as the active engine at startup

### Scenario: Configuration Specifies an Unknown Engine

- **WHEN** the configuration has `asr_model = "nonexistent"` and no such engine is registered
- **THEN** the system SHALL log a warning and remain with no active engine

## Requirements

### Requirement: ASR Engine Protocol

The system SHALL define an `ASREngine` Protocol with the following methods: `load_model(model_path, config)`, `recognize(audio) -> ASRResult`, `recognize_stream(chunk) -> PartialResult`, `set_hot_words(words)`, `set_context(context_text)`, `get_supported_languages() -> list[str]`, and `unload()`. The Protocol SHALL also include a read-only `supports_hot_words: bool` property indicating whether the engine natively supports hot word boosting. All ASR engine implementations SHALL conform to this Protocol.

#### Scenario: Mock Engine Conforms to Protocol

- **WHEN** a mock engine class implements all Protocol methods and the `supports_hot_words` property
- **THEN** the type system SHALL accept it as a valid ASREngine

#### Scenario: Engine Missing a Method

- **WHEN** a class is missing the `recognize` method
- **THEN** it SHALL NOT satisfy the ASREngine Protocol

#### Scenario: Engine reports hot words support

- **WHEN** `supports_hot_words` is queried on a sherpa-onnx engine
- **THEN** it SHALL return `True`

#### Scenario: Engine reports no hot words support

- **WHEN** `supports_hot_words` is queried on a Qwen3-ASR engine
- **THEN** it SHALL return `False`


<!-- @trace
source: hot-words-engine-sync
updated: 2026-03-07
code:
  - airtype/core/asr_qwen_pytorch.py
  - locales/zh_CN.json
  - airtype/core/asr_qwen_openvino.py
  - airtype/ui/settings_window.py
  - locales/zh_TW.json
  - airtype/core/asr_qwen_vulkan.py
  - airtype/core/asr_sherpa.py
  - airtype/core/asr_breeze.py
  - airtype/core/asr_engine.py
  - airtype/__main__.py
  - airtype/ui/settings_dictionary.py
  - locales/en.json
  - locales/ja.json
tests:
  - tests/test_asr_engine.py
  - tests/test_asr_sherpa.py
-->

---
### Requirement: ASR Result Data Model

Recognition results SHALL be returned as an `ASRResult` dataclass containing: `text` (str), `language` (str), `confidence` (float, 0.0–1.0), and `segments` (list of text segments with timestamps). Streaming partial results SHALL use a `PartialResult` dataclass containing: `text` (str) and `is_final` (bool).

#### Scenario: Full Recognition Result

- **WHEN** an engine completes batch recognition
- **THEN** the result SHALL contain text, language code, confidence score, and a list of segments

#### Scenario: Streaming Partial Result

- **WHEN** an engine produces a streaming partial result
- **THEN** the result SHALL contain the partial text and an is_final flag

---
### Requirement: Engine Registry

The system SHALL maintain an `ASREngineRegistry` that maps string engine IDs to factory callables. Engines SHALL be registered via `register_engine(id, factory)`. `get_engine(id)` SHALL return a new engine instance.

#### Scenario: Register and Retrieve Engine

- **WHEN** an engine factory is registered with the ID "mock-engine"
- **THEN** `get_engine("mock-engine")` SHALL return a valid engine instance

#### Scenario: Retrieve Unregistered Engine

- **WHEN** `get_engine("nonexistent")` is called
- **THEN** the system SHALL raise a `KeyError`

---
### Requirement: Runtime Engine Switching

The system SHALL support switching the active ASR engine at runtime via `set_active_engine(id)`. The switch SHALL unload the current engine before loading the new one. After a successful switch, the registry SHALL invoke the `on_engine_changed` callback (if set) with the new engine ID.

#### Scenario: Switch Active Engine

- **WHEN** `set_active_engine("engine-b")` is called while engine-a is active
- **THEN** engine-a SHALL be unloaded and engine-b SHALL become the active engine

#### Scenario: Engine changed callback invoked after switch

- **WHEN** `set_active_engine("engine-b")` is called and `on_engine_changed` callback is set
- **THEN** the callback SHALL be invoked with `"engine-b"` after the switch completes

#### Scenario: No callback set

- **WHEN** `set_active_engine("engine-b")` is called and `on_engine_changed` is None
- **THEN** the switch SHALL complete normally without error


<!-- @trace
source: hot-words-engine-sync
updated: 2026-03-07
code:
  - airtype/core/asr_qwen_pytorch.py
  - locales/zh_CN.json
  - airtype/core/asr_qwen_openvino.py
  - airtype/ui/settings_window.py
  - locales/zh_TW.json
  - airtype/core/asr_qwen_vulkan.py
  - airtype/core/asr_sherpa.py
  - airtype/core/asr_breeze.py
  - airtype/core/asr_engine.py
  - airtype/__main__.py
  - airtype/ui/settings_dictionary.py
  - locales/en.json
  - locales/ja.json
tests:
  - tests/test_asr_engine.py
  - tests/test_asr_sherpa.py
-->

---
### Requirement: Load Default Engine from Configuration

At startup, the system SHALL resolve the ASR engine to load by combining `voice.asr_model` (model name) and `voice.asr_inference_backend` (backend preference) configuration settings.

The resolution strategy SHALL follow this order:

1. If `voice.asr_model` directly matches a registered engine ID, the system SHALL use it as-is (backward compatibility).
2. If `voice.asr_model` matches a model name in the model-to-engine mapping, the system SHALL select an engine from the candidate list based on the `voice.asr_inference_backend` setting:
   - When backend is `"auto"`, the system SHALL iterate through the candidate engine list in priority order and select the first engine that is registered in the engine registry.
   - When backend is a specific value (e.g., `"openvino"`, `"vulkan"`, `"mlx"`), the system SHALL select the first candidate engine whose ID contains the backend string as a substring.
3. If no engine can be resolved, the system SHALL log a warning and remain with no active engine.

The `_MODEL_ENGINE_MAP` SHALL include `"qwen3-mlx"` in the candidate list for `"qwen3-asr-0.6b"`.

#### Scenario: Model Name Resolves to MLX Engine on Apple Silicon

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "auto"`, and only the engine `"qwen3-mlx"` is registered (macOS Apple Silicon)
- **THEN** the system SHALL resolve to `"qwen3-mlx"` and load it as the active engine

#### Scenario: Model Name Resolves via MLX Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "mlx"`
- **THEN** the system SHALL resolve to `"qwen3-mlx"` and load it as the active engine

#### Scenario: Model Name Resolves to Registered Engine via Auto Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "auto"`, and the engine `"qwen3-vulkan"` is registered but `"qwen3-openvino"` and `"qwen3-pytorch-cuda"` are not registered
- **THEN** the system SHALL resolve to `"qwen3-vulkan"` and load it as the active engine

#### Scenario: Model Name Resolves via Specific Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "openvino"`, and the engine `"qwen3-openvino"` is registered
- **THEN** the system SHALL resolve to `"qwen3-openvino"` and load it as the active engine

#### Scenario: Direct Engine ID Still Works

- **WHEN** the configuration has `asr_model = "qwen3-vulkan"` (which is a registered engine ID)
- **THEN** the system SHALL load `"qwen3-vulkan"` directly without consulting the model-to-engine mapping

#### Scenario: Model Name With No Registered Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and none of the candidate engines are registered
- **THEN** the system SHALL log a warning and remain with no active engine

#### Scenario: Configuration Specifies an Unknown Model

- **WHEN** the configuration has `asr_model = "nonexistent"` and it is neither a registered engine ID nor a known model name
- **THEN** the system SHALL log a warning and remain with no active engine

<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->