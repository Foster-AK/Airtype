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

The engine SHALL support hot words via the sherpa-onnx native `hotwords_file` parameter for supported models. When `set_hot_words()` is called, the engine SHALL write a temporary file in sherpa-onnx hotwords format (`word :weight` per line) and pass it to the OfflineRecognizer via the `hotwords_file` parameter. The `_build_offline_recognizer()` method SHALL include `hotwords_file=self._hotwords_file_path` when building both SenseVoice and Paraformer recognizers, provided that `self._hotwords_file_path` is not None.

#### Scenario: Load hot words

- **WHEN** `set_hot_words([HotWord("PostgreSQL", 9)])` is called
- **THEN** the hot words SHALL be written to a temporary file in `word :weight` format (e.g., `PostgreSQL :9`)
- **THEN** the temporary file SHALL be passed to the recognizer via `hotwords_file` parameter

#### Scenario: Hot words file format includes weight

- **WHEN** hot words are written to the temporary file
- **THEN** each line SHALL follow the format `word :weight` where weight is an integer
- **THEN** one hot word entry SHALL occupy exactly one line

#### Scenario: Recognizer rebuilt with hotwords_file

- **WHEN** `set_hot_words()` is called while the engine is already loaded
- **THEN** the OfflineRecognizer SHALL be rebuilt with the updated `hotwords_file` parameter
- **THEN** subsequent recognition calls SHALL use the new hot words

#### Scenario: No hot words configured

- **WHEN** `set_hot_words([])` is called with an empty list
- **THEN** `hotwords_file` SHALL NOT be passed to the recognizer factory method
- **THEN** recognition SHALL proceed without hot word boosting


<!-- @trace
source: fix-hot-words
updated: 2026-03-07
code:
  - airtype/core/asr_breeze.py
  - airtype/ui/settings_window.py
  - airtype/core/asr_qwen_pytorch.py
  - airtype/core/asr_qwen_openvino.py
  - airtype/__main__.py
  - locales/zh_TW.json
  - locales/zh_CN.json
  - airtype/ui/settings_dictionary.py
  - locales/en.json
  - airtype/core/asr_qwen_vulkan.py
  - airtype/core/asr_engine.py
  - locales/ja.json
  - airtype/core/asr_sherpa.py
tests:
  - tests/test_asr_sherpa.py
  - tests/test_asr_engine.py
-->

---
### Requirement: sherpa-onnx Engine Registration

The engine SHALL register as `"sherpa-sensevoice"` and `"sherpa-paraformer"` in the `ASREngineRegistry` when sherpa-onnx is available.

#### Scenario: Register when available

- **WHEN** the `sherpa_onnx` package is installed
- **THEN** both `"sherpa-sensevoice"` and `"sherpa-paraformer"` SHALL be available in the registry