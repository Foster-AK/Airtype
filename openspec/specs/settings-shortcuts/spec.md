# Spec: settings-shortcuts

## Overview

Shortcuts settings page within the Settings Panel. Lists all configurable hotkeys and their current key bindings. Provides a ShortcutRecorderWidget per hotkey for capturing new bindings via key press events, with conflict detection.

## Requirements

### Requirement: Shortcuts Settings Page

The settings panel SHALL provide a Shortcuts page listing all configurable hotkeys and their current key bindings. Each hotkey SHALL have a "Record" button for capturing a new hotkey via key press events.

#### Scenario: Record a New Shortcut

- **WHEN** the user clicks "Record" next to "Toggle Voice" and presses Ctrl+Alt+Space
- **THEN** the hotkey SHALL be updated to Ctrl+Alt+Space and SHALL be saved to the config

#### Scenario: Conflict Detection

- **WHEN** the user records a hotkey that conflicts with an existing hotkey
- **THEN** the system SHALL warn about the conflict and SHALL request confirmation
