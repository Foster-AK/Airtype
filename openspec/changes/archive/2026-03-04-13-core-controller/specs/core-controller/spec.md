## ADDED Requirements

### Requirement: Application State Machine

CoreController SHALL implement a 6-state machine: IDLE, ACTIVATING, LISTENING, PROCESSING, INJECTING, and ERROR. Transitions SHALL follow: IDLE→ACTIVATING (hotkey), ACTIVATING→LISTENING (ready), LISTENING→PROCESSING (speech ended), PROCESSING→INJECTING (recognition complete), INJECTING→IDLE (injection complete), any→ERROR (on error), any→IDLE (cancel).

#### Scenario: Normal Flow

- **WHEN** the user presses the hotkey, speaks, and then stops
- **THEN** the state SHALL transition in order: IDLE → ACTIVATING → LISTENING → PROCESSING → INJECTING → IDLE

#### Scenario: Cancel During Listening

- **WHEN** the user presses Escape while in the LISTENING state
- **THEN** the state SHALL transition directly to IDLE without performing text injection

### Requirement: QObject-Based Controller with Qt Signals

CoreController SHALL inherit from QObject and emit Qt Signals for state changes, enabling thread-safe UI updates from worker threads.

#### Scenario: UI Receives State Change

- **WHEN** the state transitions from LISTENING to PROCESSING
- **THEN** the `state_changed` Qt Signal SHALL be emitted with the new state

### Requirement: Globally Accessible Singleton Controller

A single CoreController instance SHALL be created at application startup and accessed via `get_controller()`. The controller SHALL manage the lifecycle: startup → idle → active → shutdown.

#### Scenario: Get Controller Instance

- **WHEN** `get_controller()` is called from any module
- **THEN** it SHALL return the same CoreController instance

### Requirement: State Machine Implemented via Enum and Transition Table

States SHALL be defined as a Python Enum. Valid transitions SHALL be defined in a dict-based transition table. Invalid transitions SHALL be logged and ignored.

#### Scenario: Invalid Transition Attempted

- **WHEN** a transition from IDLE to INJECTING is attempted (invalid)
- **THEN** the transition SHALL be rejected and a warning SHALL be logged
