## ADDED Requirements

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
