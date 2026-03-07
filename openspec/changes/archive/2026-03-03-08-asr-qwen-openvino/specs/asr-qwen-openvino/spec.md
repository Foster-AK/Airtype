## ADDED Requirements

### Requirement: OpenVINO INT8 Model Loading

The system SHALL load the Qwen3-ASR INT8 quantized OpenVINO IR model from `models/asr/qwen3_asr_int8/` using `openvino.Core().compile_model()`. The engine SHALL support both 0.6B and 1.7B model variants.

#### Scenario: Load 0.6B model

- **WHEN** `QwenOpenVinoEngine.load_model("models/asr/qwen3_asr_int8/")` is called
- **THEN** the model SHALL be compiled and ready for inference

#### Scenario: Model directory missing

- **WHEN** the model directory does not exist
- **THEN** the system SHALL raise a `FileNotFoundError` with instructions to download the model

### Requirement: Batch Speech Recognition

The engine SHALL accept preprocessed Mel-spectrogram features (from numpy-preprocessor) and return recognized text as an `ASRResult` containing text, language, and confidence score.

#### Scenario: Recognize Mandarin speech

- **WHEN** a 5-second Mandarin Chinese audio segment is processed
- **THEN** the result SHALL contain Chinese text with confidence > 0.5

### Requirement: Context Biasing via Prompt Injection

The engine SHALL support injecting hot words and context text into BPE prompt tokens to improve recognition accuracy for domain-specific terminology.

#### Scenario: Hot words boost recognition

- **WHEN** hot words `["PostgreSQL", "鼎新"]` are configured before recognition
- **THEN** those terms SHALL receive higher recognition priority

### Requirement: Lazy Model Loading

The model SHALL NOT be loaded at application startup. It SHALL be loaded on first use (first call to `recognize()`). Subsequent calls SHALL reuse the already-loaded model.

#### Scenario: First recognition triggers loading

- **WHEN** `recognize()` is called for the first time
- **THEN** the model SHALL be loaded before processing, and subsequent calls SHALL NOT reload the model

### Requirement: Engine Registration

The engine SHALL register itself as `"qwen3-openvino"` in the `ASREngineRegistry` when the `openvino` package is available. If `openvino` is not installed, the engine SHALL NOT register.

#### Scenario: Register when openvino is available

- **WHEN** the `openvino` package is installed
- **THEN** `"qwen3-openvino"` SHALL be available in the engine registry
