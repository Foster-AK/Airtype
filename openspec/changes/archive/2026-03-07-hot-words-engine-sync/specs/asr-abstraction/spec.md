## MODIFIED Requirements

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
