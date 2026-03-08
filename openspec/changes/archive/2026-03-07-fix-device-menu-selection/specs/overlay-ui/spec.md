## MODIFIED Requirements

### Requirement: Audio Device Selector

The capsule SHALL provide audio input device selection via a dropdown arrow button (QToolButton + QMenu) instead of a QComboBox. The dropdown SHALL list all available input devices and indicate the currently selected device using a checkmark indicator. The menu SHALL use a QActionGroup in exclusive mode to ensure exactly one device is checked at any time. The existing `list_input_devices()` function SHALL be reused for device enumeration.

#### Scenario: Switch Device from Capsule

- **WHEN** the user clicks the dropdown arrow button and selects a different microphone from the popup menu
- **THEN** audio capture SHALL switch to the selected device

#### Scenario: Current Device Indicated on Menu Open

- **WHEN** the user opens the device dropdown menu
- **THEN** the menu item matching `config.voice.input_device` SHALL display a checkmark indicator
- **THEN** all other menu items SHALL NOT display a checkmark

#### Scenario: Checkmark Follows Selection

- **WHEN** the user selects a different device from the menu
- **THEN** the checkmark SHALL move to the newly selected device
- **THEN** the previously selected device SHALL no longer display a checkmark

#### Scenario: Checkmark Visible on Dark Background

- **WHEN** the device menu is displayed with the dark theme stylesheet
- **THEN** the checkmark indicator SHALL be clearly visible against the dark background
