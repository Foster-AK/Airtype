# Spec: asr-sherpa

## Purpose

Defines the requirements for the sherpa-onnx ASR engine implementation. This engine wraps `sherpa_onnx.OfflineRecognizer` and `sherpa_onnx.OnlineRecognizer` to support batch and streaming recognition with SenseVoice and Paraformer models, including native hot words integration.

## Requirements

### Requirement: sherpa-onnx Offline Recognition

The system SHALL implement `SherpaOnnxEngine` to perform batch recognition using `sherpa_onnx.OfflineRecognizer` with SenseVoice and Paraformer models. The engine SHALL conform to the ASREngine Protocol.

#### Scenario: SenseVoice recognition

- **WHEN** a SenseVoice model is loaded and Chinese speech is processed
- **THEN** the result SHALL contain the recognized Chinese text

---
### Requirement: sherpa-onnx Streaming Recognition

The engine SHALL support streaming recognition via `sherpa_onnx.OnlineRecognizer` for models that support streaming (Zipformer, streaming Paraformer variants).

#### Scenario: Streaming partial results

- **WHEN** audio chunks are fed into the streaming recognizer
- **THEN** partial text results SHALL be emitted as `PartialResult` objects

---
### Requirement: sherpa-onnx Hot Words

The engine SHALL support hot words via the sherpa-onnx native `hotwords_file` parameter for supported models.

#### Scenario: Load hot words

- **WHEN** `set_hot_words([HotWord("PostgreSQL", 9)])` is called
- **THEN** the hot words SHALL be written to a temporary file and passed to the recognizer

---
### Requirement: sherpa-onnx Engine Registration

The engine SHALL register as `"sherpa-sensevoice"` and `"sherpa-paraformer"` in the `ASREngineRegistry` when sherpa-onnx is available.

#### Scenario: Register when available

- **WHEN** the `sherpa_onnx` package is installed
- **THEN** both `"sherpa-sensevoice"` and `"sherpa-paraformer"` SHALL be available in the registry
