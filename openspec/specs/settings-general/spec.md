# Spec: settings-general

## Overview

General settings page within the Settings Panel. Provides language, launch behaviour, silence timeout, text injection, notification, and logging controls. All changes are auto-saved via a debounced config write with no explicit Save button required. The Settings Panel uses QListWidget for left-side navigation and QStackedWidget for right-side content area.

## Requirements

### Requirement: General Settings Page

The settings panel SHALL provide a General settings page containing the following controls: language (dropdown), launch at login (toggle), minimize on launch (toggle), silence timeout (slider 0.5–5.0 seconds), append space (toggle), append newline (toggle), notifications (toggle), and log level (dropdown).

#### Scenario: Change Silence Timeout

- **WHEN** the user adjusts the silence timeout slider to 3.0 seconds
- **THEN** the config SHALL update to `general.silence_timeout = 3.0` and SHALL be saved automatically

---
### Requirement: QStackedWidget Tab Content Switching

The settings window SHALL use a QListWidget as the left-side navigation and a QStackedWidget as the right-side content area. Clicking a navigation item SHALL switch the displayed page.

#### Scenario: Navigate Between Tabs

- **WHEN** the user clicks "Voice" in the left-side navigation
- **THEN** the Voice settings page SHALL be displayed in the right-side content area

---
### Requirement: Auto-Save on Widget Change

All settings changes SHALL be auto-saved via debounced config writes. An explicit "Save" button SHALL NOT be required.

#### Scenario: Auto-Save After Change

- **WHEN** the user toggles the notifications switch
- **THEN** the config file SHALL be updated within 500ms
