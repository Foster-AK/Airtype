## ADDED Requirements

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
