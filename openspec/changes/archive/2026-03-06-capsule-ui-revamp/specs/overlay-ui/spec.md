## ADDED Requirements

### Requirement: Microphone Toggle Button

The capsule SHALL include a microphone toggle button (QToolButton, 32x32 pixels) positioned to the right of the vertical separator. When the application is in the IDLE state, the button SHALL display a microphone icon. When the application is in any non-IDLE state (ACTIVATING, LISTENING, PROCESSING, INJECTING, ERROR), the button SHALL display a stop icon. Clicking the button in IDLE state SHALL invoke `CoreController.request_start()`. Clicking the button in any non-IDLE state SHALL invoke `CoreController.request_stop()`. The icons SHALL be rendered programmatically using QPainter (no external image resources).

#### Scenario: Start Recording via Button

- **WHEN** the application is in IDLE state and the user clicks the microphone button
- **THEN** the button SHALL invoke `CoreController.request_start()` and the icon SHALL change to a stop icon

#### Scenario: Stop Recording via Button

- **WHEN** the application is in LISTENING state and the user clicks the stop button
- **THEN** the button SHALL invoke `CoreController.request_stop()` and the icon SHALL change to a microphone icon after returning to IDLE

### Requirement: Device Dropdown Button

The capsule SHALL include a dropdown arrow button (QToolButton, 20x32 pixels) positioned immediately to the right of the microphone button. The button SHALL use `QToolButton.InstantPopup` mode with a QMenu listing all available audio input devices. The first menu item SHALL be "Default Microphone" with data value "default". Selecting a device from the menu SHALL update `config.voice.input_device`. The device list SHALL be populated using the existing `list_input_devices()` function from `device_selector.py`.

#### Scenario: Select Device from Dropdown

- **WHEN** the user clicks the dropdown arrow and selects a different microphone from the menu
- **THEN** the configuration `voice.input_device` SHALL be updated to the selected device name

#### Scenario: Default Device Option

- **WHEN** the user opens the device dropdown menu
- **THEN** the first item SHALL be "Default Microphone" with data value "default"

### Requirement: Vertical Separator

The capsule body SHALL include a vertical separator line (QFrame VLine, 1 pixel wide, 24 pixels tall) positioned between the waveform widget and the microphone button. The separator SHALL be rendered with semi-transparent white color (rgba 255, 255, 255, 0.3).

#### Scenario: Separator Visible Between Waveform and Controls

- **WHEN** the capsule is displayed
- **THEN** a vertical separator line SHALL be visible between the waveform area and the microphone button

### Requirement: Status Label Below Capsule

The capsule SHALL display the status text label below the capsule body (not inside it). The status label SHALL be centered horizontally, use 11px font size, and have a transparent background. The status label SHALL be hidden when the application is in IDLE state and SHALL be visible in all other states.

#### Scenario: Status Hidden in IDLE

- **WHEN** the application state is IDLE
- **THEN** the status label below the capsule SHALL NOT be visible

#### Scenario: Status Visible When Listening

- **WHEN** the application state transitions to LISTENING
- **THEN** the status label below the capsule SHALL be visible and display the localized listening text

### Requirement: CapsuleBody Separation

The capsule rounded-rectangle background SHALL be painted only on the CapsuleBody inner widget, not on the full CapsuleOverlay container. The CapsuleOverlay SHALL use a QVBoxLayout containing the CapsuleBody and the status label. The CapsuleBody SHALL have a fixed height of 48 pixels.

#### Scenario: Background Does Not Cover Status Label

- **WHEN** the capsule is displayed with status text visible
- **THEN** the rounded-rectangle background SHALL cover only the CapsuleBody area and SHALL NOT extend to the status label below

## MODIFIED Requirements

### Requirement: Waveform Animation

The capsule SHALL display 7 dynamic waveform bars driven by real-time audio RMS values. The waveform bars SHALL animate using sine wave superposition with random perturbation. The animation SHALL use QPainter-based custom waveform rendering at ≥30 FPS. The WaveformWidget SHALL use a minimum width of 80 pixels and a fixed height of 32 pixels, and SHALL expand to fill available horizontal space (stretch factor 1) to achieve centered visual placement within the capsule body.

#### Scenario: Waveform During Speech

- **WHEN** the user speaks into the microphone
- **THEN** the waveform bars SHALL animate proportionally to the audio volume

#### Scenario: Waveform Fills Available Space

- **WHEN** the capsule is displayed
- **THEN** the waveform widget SHALL expand to fill the horizontal space between the left margin and the vertical separator

### Requirement: Audio Device Selector

The capsule SHALL provide audio input device selection via a dropdown arrow button (QToolButton + QMenu) instead of a QComboBox. The dropdown SHALL list all available input devices and indicate the currently selected device. The existing `list_input_devices()` function SHALL be reused for device enumeration.

#### Scenario: Switch Device from Capsule

- **WHEN** the user clicks the dropdown arrow button and selects a different microphone from the popup menu
- **THEN** audio capture SHALL switch to the selected device

### Requirement: Capsule Position Persistence

The capsule position SHALL be stored in the configuration file and SHALL be restored on the next appearance. The capsule SHALL support drag-to-reposition on the CapsuleBody area. Clicking on the microphone button or dropdown button SHALL NOT trigger drag behavior. The capsule width SHALL be 220 pixels. The CapsuleBody height SHALL be 48 pixels.

#### Scenario: Remember Position After Drag

- **WHEN** the user drags the capsule body to a new position
- **THEN** the capsule SHALL appear at the saved position on its next appearance

#### Scenario: Button Click Does Not Trigger Drag

- **WHEN** the user clicks the microphone button or dropdown button
- **THEN** the capsule SHALL NOT start a drag operation
