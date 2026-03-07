## ADDED Requirements

### Requirement: Voice Settings Page

The settings panel SHALL provide a Voice/ASR settings page containing: input device dropdown (dynamic), a refresh button, a volume slider with volume meter, noise suppression toggle, ASR model dropdown, recognition language dropdown, recognition mode options (batch/stream), and stream preview toggle.

#### Scenario: Switch ASR Model

- **WHEN** the user selects "breeze-asr-25" from the ASR model dropdown
- **THEN** the config SHALL be updated and the ASR engine SHALL switch on the next recognition

#### Scenario: Test Microphone

- **WHEN** the user clicks the test button
- **THEN** the system SHALL record for 3 seconds, play back the recording, and SHALL display the volume level
