## ADDED Requirements

### Requirement: Speech Probability Detection

The system SHALL process 512-sample (32ms) audio frames through the Silero VAD v5 ONNX model and return a speech probability value between 0.0 and 1.0 for each frame.

#### Scenario: Speech frame

- **WHEN** an audio frame containing speech is processed
- **THEN** the speech probability SHALL be greater than 0.5

#### Scenario: Silence frame

- **WHEN** an audio frame containing silence is processed
- **THEN** the speech probability SHALL be less than 0.3

### Requirement: VAD State Machine

The system SHALL implement a state machine with four states: IDLE, SPEECH, SILENCE_COUNTING, and SPEECH_ENDED. Transitions SHALL follow: IDLE → SPEECH (when `speech_prob >= threshold`), SPEECH → SILENCE_COUNTING (when `speech_prob < threshold`), SILENCE_COUNTING → SPEECH (when `speech_prob >= threshold`), SILENCE_COUNTING → SPEECH_ENDED (when silence duration >= `silence_timeout`).

#### Scenario: Speech detected from idle

- **WHEN** the VAD is in IDLE state and a frame with `speech_prob >= 0.5` is processed
- **THEN** the state SHALL transition to SPEECH

#### Scenario: Silence during speech

- **WHEN** the VAD is in SPEECH state and a frame with `speech_prob < 0.5` is processed
- **THEN** the state SHALL transition to SILENCE_COUNTING

#### Scenario: Speech resumes during silence counting

- **WHEN** the VAD is in SILENCE_COUNTING state and a frame with `speech_prob >= 0.5` is processed
- **THEN** the state SHALL transition back to SPEECH

#### Scenario: Silence timeout triggers speech end

- **WHEN** the VAD is in SILENCE_COUNTING state and silence has lasted >= the configured timeout (default 1.5s)
- **THEN** the state SHALL transition to SPEECH_ENDED

### Requirement: Configurable Parameters

The VAD SHALL support a configurable speech threshold (default 0.5) and silence timeout (range 0.5s to 5.0s, default 1.5s). These values SHALL be read from the application configuration (`general.silence_timeout`).

#### Scenario: Custom silence timeout

- **WHEN** the configuration specifies `silence_timeout = 3.0`
- **THEN** the VAD SHALL wait for 3.0 seconds of continuous silence before transitioning to SPEECH_ENDED

### Requirement: State Transition Events

The system SHALL emit a callback event on every state transition, providing the previous state and the new state. Consumers SHALL register callbacks via `on_state_change(callback)`.

#### Scenario: Callback on speech start

- **WHEN** the VAD transitions from IDLE to SPEECH
- **THEN** all registered callbacks SHALL be called with `(previous=IDLE, current=SPEECH)`
