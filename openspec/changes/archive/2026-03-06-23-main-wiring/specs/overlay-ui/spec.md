## ADDED Requirements

### Requirement: State-Driven Waveform Animation Control

CapsuleOverlay.set_state() SHALL call WaveformWidget.set_active() to start or stop the waveform animation timer based on the current application state. The animation SHALL be active only during LISTENING and PROCESSING states to reduce idle CPU usage.

#### Scenario: Animation Starts on Listening

- **WHEN** the application state transitions to LISTENING
- **THEN** WaveformWidget.set_active(True) SHALL be called
- **THEN** the waveform animation timer SHALL be running

#### Scenario: Animation Stops on Idle

- **WHEN** the application state transitions to IDLE
- **THEN** WaveformWidget.set_active(False) SHALL be called
- **THEN** the waveform animation timer SHALL be stopped
