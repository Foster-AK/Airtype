## ADDED Requirements

### Requirement: ASR Engine Protocol

The system SHALL define an `ASREngine` Protocol with the following methods: `load_model(model_path, config)`, `recognize(audio) -> ASRResult`, `recognize_stream(chunk) -> PartialResult`, `set_hot_words(words)`, `set_context(context_text)`, `get_supported_languages() -> list[str]`, and `unload()`. All ASR engine implementations SHALL conform to this Protocol.

#### Scenario: Mock Engine Conforms to Protocol

- **WHEN** a mock engine class implements all Protocol methods
- **THEN** the type system SHALL accept it as a valid ASREngine

#### Scenario: Engine Missing a Method

- **WHEN** a class is missing the `recognize` method
- **THEN** it SHALL NOT satisfy the ASREngine Protocol

### Requirement: ASR Result Data Model

Recognition results SHALL be returned as an `ASRResult` dataclass containing: `text` (str), `language` (str), `confidence` (float, 0.0–1.0), and `segments` (list of text segments with timestamps). Streaming partial results SHALL use a `PartialResult` dataclass containing: `text` (str) and `is_final` (bool).

#### Scenario: Full Recognition Result

- **WHEN** an engine completes batch recognition
- **THEN** the result SHALL contain text, language code, confidence score, and a list of segments

#### Scenario: Streaming Partial Result

- **WHEN** an engine produces a streaming partial result
- **THEN** the result SHALL contain the partial text and an is_final flag

### Requirement: Engine Registry

The system SHALL maintain an `ASREngineRegistry` that maps string engine IDs to factory callables. Engines SHALL be registered via `register_engine(id, factory)`. `get_engine(id)` SHALL return a new engine instance.

#### Scenario: Register and Retrieve Engine

- **WHEN** an engine factory is registered with the ID "mock-engine"
- **THEN** `get_engine("mock-engine")` SHALL return a valid engine instance

#### Scenario: Retrieve Unregistered Engine

- **WHEN** `get_engine("nonexistent")` is called
- **THEN** the system SHALL raise a `KeyError`

### Requirement: Runtime Engine Switching

The system SHALL support switching the active ASR engine at runtime via `set_active_engine(id)`. The switch SHALL unload the current engine before loading the new one.

#### Scenario: Switch Active Engine

- **WHEN** `set_active_engine("engine-b")` is called while engine-a is active
- **THEN** engine-a SHALL be unloaded and engine-b SHALL become the active engine

### Requirement: Load Default Engine from Configuration

At startup, the system SHALL load the ASR engine specified by the `voice.asr_model` configuration setting. If the specified engine is not registered, the system SHALL log a warning and remain with no active engine.

#### Scenario: Configuration Specifies a Valid Engine

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and that engine is registered
- **THEN** the system SHALL load it as the active engine at startup

#### Scenario: Configuration Specifies an Unknown Engine

- **WHEN** the configuration has `asr_model = "nonexistent"` and no such engine is registered
- **THEN** the system SHALL log a warning and remain with no active engine
