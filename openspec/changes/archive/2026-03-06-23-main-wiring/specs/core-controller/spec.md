## ADDED Requirements

### Requirement: PROCESSING State Timeout Protection

CoreController SHALL implement a 30-second timeout for the PROCESSING state using a single-shot QTimer. If the timeout expires before recognition completes, the controller SHALL call set_error() to transition back to IDLE.

#### Scenario: ASR Timeout Recovery

- **WHEN** the state transitions to PROCESSING and no recognition result arrives within 30 seconds
- **THEN** the controller SHALL call set_error("辨識超時") and transition to IDLE

#### Scenario: Timeout Cancelled on Recognition Complete

- **WHEN** on_recognition_complete() is called before the timeout expires
- **THEN** the timeout timer SHALL be cancelled

#### Scenario: Timeout Cancelled on Cancel

- **WHEN** cancel() is called while in PROCESSING state
- **THEN** the timeout timer SHALL be cancelled

### Requirement: Manual Stop Triggers Pipeline Flush

When the user presses the stop hotkey during LISTENING state, _on_hotkey_stop() SHALL call pipeline.flush_and_recognize() to force ASR processing of accumulated audio, rather than relying solely on VAD SPEECH_ENDED events.

#### Scenario: Manual Stop with Pipeline

- **WHEN** the user presses the stop hotkey while in LISTENING state and a pipeline is connected
- **THEN** the controller SHALL transition to PROCESSING
- **THEN** the controller SHALL call pipeline.flush_and_recognize()

#### Scenario: Manual Stop without Pipeline

- **WHEN** the user presses the stop hotkey while in LISTENING state and no pipeline is connected
- **THEN** the controller SHALL call cancel() to return to IDLE immediately

### Requirement: Empty Recognition Result Handling

When on_recognition_complete() receives an empty text string, the controller SHALL transition directly to IDLE without attempting text injection.

#### Scenario: Empty Recognition Result

- **WHEN** on_recognition_complete("") is called
- **THEN** the controller SHALL transition to IDLE
- **THEN** no text injection SHALL occur
