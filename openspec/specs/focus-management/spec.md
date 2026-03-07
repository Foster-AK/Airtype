# Focus Management Spec

## Purpose

Defines the behavior of focus window recording and restoration for Airtype's voice input workflow. The system captures the active window when voice input begins and restores focus to that window after text injection is complete, ensuring a seamless user experience across Windows, macOS, and Linux.

## Requirements

### Requirement: Record Active Window

The system SHALL record the currently focused window when voice input is activated. The recorded information SHALL be sufficient to restore focus to that window at a later time.

#### Scenario: Record from VS Code

- **WHEN** the user activates voice input while VS Code is the foreground window
- **THEN** the system SHALL record VS Code as the target window for subsequent focus restoration

#### Scenario: Record from any application

- **WHEN** the user activates voice input from any foreground application
- **THEN** the system SHALL record the application's window handle (Windows), application name (macOS), or window ID (Linux)

---
### Requirement: Restore Focus

The system SHALL restore focus to the previously recorded window after speech recognition is complete. Focus restoration SHALL complete within 100ms of being called.

#### Scenario: Restore after text injection

- **WHEN** text injection is complete and focus restoration is triggered
- **THEN** the previously recorded window SHALL become the foreground window within 100ms

#### Scenario: Target window has been closed

- **WHEN** focus restoration is triggered but the previously recorded window no longer exists
- **THEN** the system SHALL log a warning and SHALL NOT crash

---
### Requirement: Cross-Platform Focus Operations

Focus management SHALL use platform-specific APIs: Win32 API on Windows (`GetForegroundWindow` / `SetForegroundWindow` with `AttachThreadInput`), osascript / AppKit on macOS, and xdotool on Linux.

#### Scenario: Windows focus management

- **WHEN** the system is running on Windows
- **THEN** recording SHALL use `GetForegroundWindow` via ctypes
- **AND** restoration SHALL use `SetForegroundWindow` with `AttachThreadInput` via ctypes

#### Scenario: macOS focus management

- **WHEN** the system is running on macOS
- **THEN** recording SHALL use osascript to query the frontmost application
- **AND** restoration SHALL use osascript to activate the recorded application

#### Scenario: Linux focus management

- **WHEN** the system is running on Linux (X11)
- **THEN** recording SHALL use `xdotool getactivewindow` to obtain the active window ID
- **AND** restoration SHALL use `xdotool windowactivate` to restore focus to that window

---
### Requirement: FocusManager Interface

All platform-specific focus operations SHALL be encapsulated behind a `FocusManager` abstract interface with `record()` and `restore()` methods. A factory function SHALL return the correct platform-specific implementation based on `sys.platform`.

#### Scenario: Factory returns correct implementation

- **WHEN** `FocusManager` is instantiated on Windows
- **THEN** the factory SHALL return a `WindowsFocusManager` instance
- **AND** on macOS it SHALL return a `MacOSFocusManager`
- **AND** on Linux it SHALL return a `LinuxFocusManager`
