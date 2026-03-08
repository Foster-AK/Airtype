## MODIFIED Requirements

### Requirement: Device Dropdown Button

The capsule SHALL include a dropdown arrow button (QToolButton, 20x32 pixels) positioned immediately to the right of the microphone button. The button SHALL use `QToolButton.InstantPopup` mode with a QMenu listing all available audio input devices. The first menu item SHALL be "Default Microphone" with data value "default". Selecting a device from the menu SHALL update `config.voice.input_device`. The device list SHALL be populated using the existing `list_input_devices()` function from `device_selector.py`. CapsuleOverlay SHALL declare a `device_changed = Signal(str)` class-level signal. When the user selects a device from the dropdown menu, `_on_device_selected()` SHALL emit `device_changed` with the selected device name after updating config, enabling external components to react to the device change.

#### Scenario: Select Device from Dropdown

- **WHEN** the user clicks the dropdown arrow and selects a different microphone from the menu
- **THEN** the configuration `voice.input_device` SHALL be updated to the selected device name
- **THEN** CapsuleOverlay SHALL emit `device_changed` with the selected device name

#### Scenario: Default Device Option

- **WHEN** the user opens the device dropdown menu
- **THEN** the first item SHALL be "Default Microphone" with data value "default"
