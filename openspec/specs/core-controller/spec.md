# Spec: Core Controller

## Requirement: Application State Machine

CoreController SHALL implement a 6-state machine: IDLE, ACTIVATING, LISTENING, PROCESSING, INJECTING, and ERROR. Transitions SHALL follow: IDLE→ACTIVATING (hotkey), ACTIVATING→LISTENING (ready), LISTENING→PROCESSING (speech ended), PROCESSING→INJECTING (recognition complete), INJECTING→IDLE (injection complete), any→ERROR (on error), any→IDLE (cancel).

### Scenario: Normal Flow

- **WHEN** the user presses the hotkey, speaks, and then stops
- **THEN** the state SHALL transition in order: IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE

### Scenario: Cancel During Listening

- **WHEN** the user presses Escape while in the LISTENING state
- **THEN** the state SHALL transition directly to IDLE without performing text injection

## Requirement: QObject-Based Controller with Qt Signals

CoreController SHALL inherit from QObject and emit Qt Signals for state changes, enabling thread-safe UI updates from worker threads.

### Scenario: UI Receives State Change

- **WHEN** the state transitions from LISTENING to PROCESSING
- **THEN** the `state_changed` Qt Signal SHALL be emitted with the new state

## Requirement: Globally Accessible Singleton Controller

A single CoreController instance SHALL be created at application startup and accessed via `get_controller()`. The controller SHALL manage the lifecycle: startup → idle → active → shutdown.

### Scenario: Get Controller Instance

- **WHEN** `get_controller()` is called from any module
- **THEN** it SHALL return the same CoreController instance

## Requirement: State Machine Implemented via Enum and Transition Table

States SHALL be defined as a Python Enum. Valid transitions SHALL be defined in a dict-based transition table. Invalid transitions SHALL be logged and ignored.

### Scenario: Invalid Transition Attempted

- **WHEN** a transition from IDLE to INJECTING is attempted (invalid)
- **THEN** the transition SHALL be rejected and a warning SHALL be logged

## Requirements

### Requirement: Application State Machine

CoreController SHALL implement a 6-state machine: IDLE, ACTIVATING, LISTENING, PROCESSING, INJECTING, and ERROR. Transitions SHALL follow: IDLE→ACTIVATING (hotkey), ACTIVATING→LISTENING (ready), LISTENING→PROCESSING (speech ended), PROCESSING→INJECTING (recognition complete), INJECTING→IDLE (injection complete), any→ERROR (on error), any→IDLE (cancel).

#### Scenario: Normal Flow

- **WHEN** the user presses the hotkey, speaks, and then stops
- **THEN** the state SHALL transition in order: IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE

#### Scenario: Cancel During Listening

- **WHEN** the user presses Escape while in the LISTENING state
- **THEN** the state SHALL transition directly to IDLE without performing text injection

---
### Requirement: QObject-Based Controller with Qt Signals

CoreController SHALL inherit from QObject and emit Qt Signals for state changes, enabling thread-safe UI updates from worker threads.

#### Scenario: UI Receives State Change

- **WHEN** the state transitions from LISTENING to PROCESSING
- **THEN** the `state_changed` Qt Signal SHALL be emitted with the new state

---
### Requirement: Globally Accessible Singleton Controller

A single CoreController instance SHALL be created at application startup and accessed via `get_controller()`. The controller SHALL manage the lifecycle: startup → idle → active → shutdown.

#### Scenario: Get Controller Instance

- **WHEN** `get_controller()` is called from any module
- **THEN** it SHALL return the same CoreController instance

---
### Requirement: State Machine Implemented via Enum and Transition Table

States SHALL be defined as a Python Enum. Valid transitions SHALL be defined in a dict-based transition table. Invalid transitions SHALL be logged and ignored.

#### Scenario: Invalid Transition Attempted

- **WHEN** a transition from IDLE to INJECTING is attempted (invalid)
- **THEN** the transition SHALL be rejected and a warning SHALL be logged

---
### Requirement: Application Bootstrap Wiring

The application entry point (`__main__.py`) SHALL instantiate a `HotkeyManager` with `config.shortcuts` and pass it to `CoreController` as the `hotkey_manager` parameter. The entry point SHALL connect `SystemTrayIcon.toggle_voice_requested` signal to the `HotkeyManager` toggle handler so that tray menu activation triggers the same state transitions as the keyboard shortcut.

#### Scenario: Hotkey triggers voice input on startup

- **WHEN** the application starts and the user presses the configured toggle hotkey (default: ctrl+shift+space)
- **THEN** the `CoreController` state SHALL transition from IDLE to ACTIVATING to LISTENING

#### Scenario: Tray menu triggers voice input

- **WHEN** the user clicks the "toggle voice input" item in the system tray context menu
- **THEN** the `HotkeyManager` toggle handler SHALL be invoked, triggering the same state transition as the keyboard shortcut

#### Scenario: Tray menu stops voice input

- **WHEN** the user clicks the "toggle voice input" item while the application is in LISTENING state
- **THEN** the `HotkeyManager` toggle handler SHALL transition the state from LISTENING to PROCESSING

---
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

---
### Requirement: Manual Stop Triggers Pipeline Flush

When the user presses the stop hotkey during LISTENING state, _on_hotkey_stop() SHALL call pipeline.flush_and_recognize() to force ASR processing of accumulated audio, rather than relying solely on VAD SPEECH_ENDED events.

#### Scenario: Manual Stop with Pipeline

- **WHEN** the user presses the stop hotkey while in LISTENING state and a pipeline is connected
- **THEN** the controller SHALL transition to PROCESSING
- **THEN** the controller SHALL call pipeline.flush_and_recognize()

#### Scenario: Manual Stop without Pipeline

- **WHEN** the user presses the stop hotkey while in LISTENING state and no pipeline is connected
- **THEN** the controller SHALL call cancel() to return to IDLE immediately

---
### Requirement: Empty Recognition Result Handling

When on_recognition_complete() receives an empty text string, the controller SHALL transition directly to IDLE without attempting text injection.

#### Scenario: Empty Recognition Result

- **WHEN** on_recognition_complete("") is called
- **THEN** the controller SHALL transition to IDLE
- **THEN** no text injection SHALL occur

---
### Requirement: Public Recording Control Methods

CoreController SHALL expose two public methods for external callers (UI buttons, tray menu) to request recording start and stop:

- `request_start()` SHALL delegate to the internal `_on_hotkey_start()` method to trigger the IDLE → ACTIVATING → LISTENING transition.
- `request_stop()` SHALL delegate to the internal `_on_hotkey_stop()` method to trigger the LISTENING → PROCESSING transition.

These methods SHALL provide a stable public API for UI components without exposing internal hotkey handler implementation details.

#### Scenario: UI Button Starts Recording

- **WHEN** `request_start()` is called while the controller is in IDLE state
- **THEN** the controller SHALL transition from IDLE to ACTIVATING and then to LISTENING

#### Scenario: UI Button Stops Recording

- **WHEN** `request_stop()` is called while the controller is in LISTENING state
- **THEN** the controller SHALL transition from LISTENING to PROCESSING

#### Scenario: Start Request Ignored When Not IDLE

- **WHEN** `request_start()` is called while the controller is in LISTENING state
- **THEN** the request SHALL be ignored and the state SHALL remain LISTENING
