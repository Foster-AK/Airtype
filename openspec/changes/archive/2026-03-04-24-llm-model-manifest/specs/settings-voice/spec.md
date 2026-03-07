## MODIFIED Requirements

### Requirement: Voice Settings Page

The settings panel SHALL provide a Voice/ASR settings page containing: input device dropdown (dynamic), a refresh button, a volume slider with volume meter, noise suppression toggle, ASR model dropdown populated dynamically from the manifest (`category="asr"`), recognition language dropdown, recognition mode options (batch/stream), and stream preview toggle. The ASR model dropdown SHALL mark the hardware-recommended model with a "(建議)" label. The user's selection SHALL be persisted to `config.voice.asr_model`.

#### Scenario: Switch ASR Model

- **WHEN** the user selects "breeze-asr-25" from the ASR model dropdown
- **THEN** the config SHALL be updated (`voice.asr_model = "breeze-asr-25"`) and the ASR engine SHALL switch on the next recognition

#### Scenario: Hardware Recommendation Highlighted

- **WHEN** the ASR model dropdown is opened
- **THEN** the model recommended by `HardwareDetector.recommend()` SHALL be marked with "(建議)" in the dropdown list

#### Scenario: Test Microphone

- **WHEN** the user clicks the test button
- **THEN** the system SHALL record for 3 seconds, play back the recording, and SHALL display the volume level

## ADDED Requirements

### Requirement: Manifest-Driven ASR Model List

The ASR model dropdown SHALL be populated by calling `ModelManager.list_models_by_category("asr")` at settings page initialization. The dropdown SHALL display each model's `description` field as the label and use its `id` field as the value. If a model is not yet downloaded, the dropdown SHALL display a download indicator alongside the model name.

#### Scenario: Models Loaded from Manifest

- **WHEN** the Voice settings page is opened
- **THEN** the ASR model dropdown SHALL contain all entries returned by `list_models_by_category("asr")` with their description as the display label

#### Scenario: Undownloaded Model Indicated

- **WHEN** a manifest ASR model is not present in the local model directory
- **THEN** the dropdown SHALL display that model with a download indicator (e.g., "↓") appended to its label
