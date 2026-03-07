## MODIFIED Requirements

### Requirement: Voice Settings Page

The settings panel SHALL provide a Voice/ASR settings page containing: input device dropdown (dynamic), a refresh button, a volume slider with volume meter, noise suppression toggle, ASR model dropdown populated dynamically from the manifest (`category="asr"`), recognition language dropdown, recognition mode options (batch/stream), and stream preview toggle. The ASR model dropdown SHALL mark the hardware-recommended model with a "(建議)" label. The user's selection SHALL be persisted to `config.voice.asr_model`. The input device dropdown SHALL display a deduplicated list of physical input devices by delegating to the shared `list_input_devices()` utility; each physical device SHALL appear exactly once regardless of the number of Host APIs that expose it.

#### Scenario: Switch ASR Model

- **WHEN** the user selects "breeze-asr-25" from the ASR model dropdown
- **THEN** the config SHALL be updated (`voice.asr_model = "breeze-asr-25"`) and the ASR engine SHALL switch on the next recognition

#### Scenario: Hardware Recommendation Highlighted

- **WHEN** the ASR model dropdown is opened
- **THEN** the model recommended by `HardwareDetector.recommend()` SHALL be marked with "(建議)" in the dropdown list

#### Scenario: Test Microphone

- **WHEN** the user clicks the test button
- **THEN** the system SHALL record for 3 seconds, play back the recording, and SHALL display the volume level

#### Scenario: Device dropdown shows no duplicates

- **WHEN** the input device dropdown is opened on a system where the same physical microphone is exposed by multiple Host APIs
- **THEN** the dropdown SHALL list each physical device exactly once, showing the entry from the platform-preferred Host API
