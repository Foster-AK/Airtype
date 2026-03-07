# Global Hotkey Spec

## Purpose

Defines the behavior of global hotkey registration and handling for Airtype's voice input activation. The system uses pynput to listen for system-wide key combinations that trigger voice recording start, stop, and cancel actions without requiring the application window to be in focus.

## Requirements

### Requirement: Hotkey Registration

The system SHALL register global hotkeys from the configuration `shortcuts` section. The default hotkey for `toggle_voice` SHALL be Ctrl+Shift+Space. Key combinations SHALL be parsed from string format (e.g., `"ctrl+shift+space"`) into pynput key sets.

#### Scenario: Register default hotkey

- **WHEN** the hotkey listener starts with default configuration
- **THEN** the system SHALL register Ctrl+Shift+Space as the `toggle_voice` hotkey
- **AND** pressing Ctrl+Shift+Space SHALL trigger the `toggle_voice` callback

#### Scenario: Custom hotkey

- **WHEN** the configuration `shortcuts` section specifies `toggle_voice: "ctrl+alt+r"`
- **THEN** the system SHALL register Ctrl+Alt+R as the `toggle_voice` hotkey
- **AND** pressing Ctrl+Alt+R SHALL trigger the `toggle_voice` callback

---
### Requirement: Hotkey Toggle Behavior

The `toggle_voice` hotkey SHALL implement toggle behavior: pressing the hotkey once SHALL trigger a start event, and pressing it again SHALL trigger a stop event. The hotkey module SHALL maintain internal state (INACTIVE / ACTIVE) to track the toggle.

#### Scenario: First press activates

- **WHEN** the hotkey is in INACTIVE state and the user presses the `toggle_voice` hotkey
- **THEN** the system SHALL trigger a start event and transition to ACTIVE state

#### Scenario: Second press deactivates

- **WHEN** the hotkey is in ACTIVE state and the user presses the `toggle_voice` hotkey
- **THEN** the system SHALL trigger a stop event and transition to INACTIVE state

---
### Requirement: Cancel Hotkey

The Escape key SHALL cancel the current recording without injecting text. Pressing Escape SHALL trigger a cancel event and reset the toggle state to INACTIVE regardless of the current state.

#### Scenario: Cancel during recording

- **WHEN** the hotkey is in ACTIVE state and the user presses Escape
- **THEN** the system SHALL trigger a cancel event and transition to INACTIVE state

#### Scenario: Cancel while inactive

- **WHEN** the hotkey is in INACTIVE state and the user presses Escape
- **THEN** the system SHALL NOT trigger any event (no-op)

---
### Requirement: Cross-Platform Hotkey Support

The hotkey listener SHALL operate on Windows, macOS, and Linux (X11). On macOS, if Accessibility permissions have not been granted, the system SHALL log an error message containing instructions for enabling access (System Preferences > Privacy & Security > Accessibility).

#### Scenario: macOS Accessibility permissions not granted

- **WHEN** the hotkey listener starts on macOS and Accessibility permissions have not been granted
- **THEN** the system SHALL log an error message containing instructions to grant Accessibility permissions
- **AND** the system SHALL NOT crash

#### Scenario: Linux Wayland detection

- **WHEN** the hotkey listener starts on Linux using the Wayland display server
- **THEN** the system SHALL log a warning that global hotkeys may not function under Wayland
