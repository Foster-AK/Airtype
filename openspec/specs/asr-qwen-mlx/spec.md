# asr-qwen-mlx Specification

## Purpose

TBD - created by archiving change 'asr-qwen-mlx'. Update Purpose after archive.

## Requirements

### Requirement: MLX Model Loading

The system SHALL provide an `MLXQwen3ASREngine` class that loads the Qwen3-ASR 0.6B model via `mlx-qwen3-asr`'s `Session` API. The engine SHALL accept a model path or HuggingFace model ID (e.g., `Qwen/Qwen3-ASR-0.6B`) and load the model using MLX safetensors format with float16 precision by default.

#### Scenario: Load model from HuggingFace ID

- **WHEN** `MLXQwen3ASREngine.load_model("Qwen/Qwen3-ASR-0.6B", {})` is called on an Apple Silicon Mac
- **THEN** the model SHALL be loaded into unified memory and ready for inference

#### Scenario: Load model from local path

- **WHEN** `MLXQwen3ASREngine.load_model("~/.airtype/models/qwen3-asr-0.6b-mlx/", {})` is called
- **THEN** the model SHALL be loaded from the local safetensors files

#### Scenario: Model directory missing

- **WHEN** the specified model path does not exist and is not a valid HuggingFace ID
- **THEN** the system SHALL raise a `FileNotFoundError` with a descriptive error message


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
### Requirement: Batch Speech Recognition

The engine SHALL accept 16kHz mono PCM float32 audio as `np.ndarray` and return an `ASRResult` containing recognized text, detected language, and confidence score. The engine SHALL delegate audio preprocessing (Mel spectrogram extraction) to `mlx-qwen3-asr`'s internal pipeline.

#### Scenario: Recognize Mandarin speech

- **WHEN** a 5-second Mandarin Chinese audio segment (16kHz mono float32 np.ndarray) is passed to `recognize()`
- **THEN** the result SHALL contain Chinese text with `confidence > 0.5` and `language` set to a valid BCP-47 code

#### Scenario: Recognize English speech

- **WHEN** a 5-second English audio segment is passed to `recognize()`
- **THEN** the result SHALL contain English text with a valid confidence score

#### Scenario: Empty audio input

- **WHEN** a zero-length or silent audio array is passed to `recognize()`
- **THEN** the result SHALL contain empty text with `confidence = 0.0`


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
### Requirement: Context Text Biasing

The engine SHALL support `set_context(context_text)` to inject domain-specific vocabulary hints via `mlx-qwen3-asr`'s `context` parameter during transcription.

#### Scenario: Context text improves recognition

- **WHEN** `set_context("PostgreSQL 鼎新")` is called before `recognize()`
- **THEN** the transcription SHALL use the context text as a bias hint for improved accuracy

#### Scenario: Clear context

- **WHEN** `set_context("")` is called
- **THEN** subsequent transcriptions SHALL proceed without context biasing


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
### Requirement: Lazy Model Loading

The engine SHALL support `prepare(model_path, config)` to set the model path without immediate loading. The model SHALL be loaded on the first call to `recognize()`. Subsequent calls SHALL reuse the loaded model.

#### Scenario: First recognition triggers loading

- **WHEN** `prepare()` is called followed by `recognize()`
- **THEN** the model SHALL be loaded before processing the first audio, and subsequent calls SHALL NOT reload the model

#### Scenario: Prepare without recognize

- **WHEN** `prepare()` is called but `recognize()` is never called
- **THEN** no model SHALL be loaded into memory


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
### Requirement: Engine Registration

The engine module SHALL provide a `register(registry)` function that registers `MLXQwen3ASREngine` with engine ID `"qwen3-mlx"` in the `ASREngineRegistry`. Registration SHALL only succeed when the `mlx` package is importable. If `mlx` is not available, registration SHALL return `False` without raising an exception.

#### Scenario: Register when mlx is available

- **WHEN** the `mlx` package is installed on macOS Apple Silicon
- **THEN** `register()` SHALL add `"qwen3-mlx"` to the registry and return `True`

#### Scenario: Skip registration when mlx is unavailable

- **WHEN** the `mlx` package is not installed (e.g., on Windows or Linux)
- **THEN** `register()` SHALL return `False` and log a debug message


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
### Requirement: Model Unloading

The engine SHALL implement `unload()` to release the MLX model from memory. After unloading, subsequent `recognize()` calls SHALL trigger a reload if `prepare()` was previously called.

#### Scenario: Unload releases memory

- **WHEN** `unload()` is called on a loaded engine
- **THEN** the internal Session and model references SHALL be set to `None`

#### Scenario: Recognize after unload with prepare

- **WHEN** `unload()` is called after `prepare()` was set, then `recognize()` is called
- **THEN** the model SHALL be reloaded and recognition SHALL succeed


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
### Requirement: Hot Words Property

The engine SHALL report `supports_hot_words` as `False`, since `mlx-qwen3-asr` uses context text biasing rather than weighted hot word injection.

#### Scenario: Hot words not supported

- **WHEN** `supports_hot_words` is queried on `MLXQwen3ASREngine`
- **THEN** it SHALL return `False`


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
### Requirement: Supported Languages

The engine SHALL report supported languages matching Qwen3-ASR's multilingual capabilities, including at minimum: `zh-TW`, `zh-CN`, `en`, `ja`, `ko`.

#### Scenario: Query supported languages

- **WHEN** `get_supported_languages()` is called
- **THEN** the returned list SHALL contain `"zh-TW"`, `"zh-CN"`, `"en"`, `"ja"`, and `"ko"`

<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->