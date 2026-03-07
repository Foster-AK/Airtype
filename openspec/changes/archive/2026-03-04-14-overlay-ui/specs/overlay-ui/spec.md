## ADDED Requirements

### Requirement: Floating Capsule Window

The overlay SHALL be a frameless, transparent, always-on-top QWidget and SHALL NOT steal focus from the user's active application. The overlay SHALL use Qt Tool window flags to implement the non-focus-stealing behavior.

#### Scenario: Capsule Appears Without Stealing Focus

- **WHEN** the capsule overlay is shown while VS Code has focus
- **THEN** VS Code SHALL remain the focused application

### Requirement: Waveform Animation

The capsule SHALL display 7 dynamic waveform bars driven by real-time audio RMS values. The waveform bars SHALL animate using sine wave superposition with random perturbation. The animation SHALL use QPainter-based custom waveform rendering at ≥30 FPS.

#### Scenario: Waveform During Speech

- **WHEN** the user speaks into the microphone
- **THEN** the waveform bars SHALL animate proportionally to the audio volume

### Requirement: Audio Device Selector

The capsule SHALL include a dropdown for selecting the audio input device. The dropdown SHALL list all available input devices and indicate the currently selected device.

#### Scenario: Switch Device from Capsule

- **WHEN** the user clicks the device dropdown and selects a different microphone
- **THEN** audio capture SHALL switch to the selected device

### Requirement: Slide Animation

The capsule SHALL animate in when appearing (slide up + fade in, 200ms) and SHALL animate out when disappearing (slide down + fade out, 150ms).

#### Scenario: Capsule Appear Animation

- **WHEN** voice input is activated
- **THEN** the capsule SHALL slide in from below with a 200ms animation

### Requirement: Capsule Position Persistence

The capsule position SHALL be stored in the configuration file and SHALL be restored on the next appearance. The capsule SHALL support drag-to-reposition.

#### Scenario: Remember Position After Drag

- **WHEN** the user drags the capsule to a new position
- **THEN** the capsule SHALL appear at the saved position on its next appearance
