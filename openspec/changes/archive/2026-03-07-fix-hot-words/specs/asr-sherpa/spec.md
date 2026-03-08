## MODIFIED Requirements

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
