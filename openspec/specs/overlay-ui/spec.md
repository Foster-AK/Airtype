# Spec: Overlay UI

## Purpose

This capability defines the floating capsule overlay widget for Airtype. It covers the non-focus-stealing frameless window, real-time waveform animation driven by audio RMS, audio device selection from within the capsule, slide/fade animations for show and hide, and drag-based position persistence across sessions.

---

## Requirements

### Requirement: Floating Capsule Window

The overlay SHALL be a frameless, transparent, always-on-top QWidget and SHALL NOT steal focus from the user's active application. The overlay SHALL use Qt Tool window flags to implement the non-focus-stealing behavior.

#### Scenario: Capsule Appears Without Stealing Focus

- **WHEN** the capsule overlay is shown while VS Code has focus
- **THEN** VS Code SHALL remain the focused application

---
### Requirement: Waveform Animation

The capsule SHALL display 7 dynamic waveform bars driven by real-time audio RMS values. The waveform bars SHALL animate using sine wave superposition with random perturbation. The animation SHALL use QPainter-based custom waveform rendering at ≥30 FPS. The WaveformWidget SHALL use a minimum width of 80 pixels and a fixed height of 32 pixels, and SHALL expand to fill available horizontal space (stretch factor 1) to achieve centered visual placement within the capsule body.

#### Scenario: Waveform During Speech

- **WHEN** the user speaks into the microphone
- **THEN** the waveform bars SHALL animate proportionally to the audio volume

#### Scenario: Waveform Fills Available Space

- **WHEN** the capsule is displayed
- **THEN** the waveform widget SHALL expand to fill the horizontal space between the left margin and the vertical separator

---
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


<!-- @trace
source: fix-device-menu-selection
updated: 2026-03-07
code:
  - airtype/__main__.py
  - airtype/core/asr_breeze.py
  - locales/ja.json
  - airtype/core/asr_sherpa.py
  - airtype/ui/settings_dictionary.py
  - airtype/core/asr_qwen_openvino.py
  - airtype/core/asr_qwen_vulkan.py
  - airtype/ui/settings_window.py
  - airtype/ui/overlay.py
  - airtype/core/asr_qwen_pytorch.py
  - locales/en.json
  - airtype/core/asr_engine.py
  - locales/zh_TW.json
  - locales/zh_CN.json
tests:
  - tests/test_asr_engine.py
  - tests/test_overlay.py
  - tests/test_asr_sherpa.py
-->

---
### Requirement: Slide Animation

The capsule SHALL animate in when appearing (slide up + fade in, 200ms) and SHALL animate out when disappearing (slide down + fade out, 150ms). The fade animation SHALL use a temporary QGraphicsOpacityEffect that is attached only during the animation and removed immediately after the animation completes. The capsule SHALL NOT retain any QGraphicsEffect during its normal visible state.

#### Scenario: Capsule Appear Animation

- **WHEN** voice input is activated
- **THEN** the capsule SHALL slide in from below with a 200ms animation

#### Scenario: No Graphics Effect After Show Animation

- **WHEN** the show animation completes
- **THEN** the capsule SHALL have no QGraphicsEffect attached
- **THEN** the capsule SHALL render directly without offscreen buffering

#### Scenario: Capsule Background Preserved After Device Switch

- **WHEN** the user switches the audio input device via the capsule DeviceSelector dropdown
- **THEN** the capsule rounded-rectangle background SHALL remain visually unchanged

---
### Requirement: Capsule Position Persistence

The capsule position SHALL be stored in the configuration file and SHALL be restored on the next appearance. The capsule SHALL support drag-to-reposition on the CapsuleBody area. Clicking on the microphone button or dropdown button SHALL NOT trigger drag behavior. The capsule width SHALL be 220 pixels. The CapsuleBody height SHALL be 48 pixels.

#### Scenario: Remember Position After Drag

- **WHEN** the user drags the capsule body to a new position
- **THEN** the capsule SHALL appear at the saved position on its next appearance

#### Scenario: Button Click Does Not Trigger Drag

- **WHEN** the user clicks the microphone button or dropdown button
- **THEN** the capsule SHALL NOT start a drag operation

---
### Requirement: State-Driven Waveform Animation Control

CapsuleOverlay.set_state() SHALL call WaveformWidget.set_active() to start or stop the waveform animation timer based on the current application state. The animation SHALL be active only during LISTENING and PROCESSING states to reduce idle CPU usage.

#### Scenario: Animation Starts on Listening

- **WHEN** the application state transitions to LISTENING
- **THEN** WaveformWidget.set_active(True) SHALL be called
- **THEN** the waveform animation timer SHALL be running

#### Scenario: Animation Stops on Idle

- **WHEN** the application state transitions to IDLE
- **THEN** WaveformWidget.set_active(False) SHALL be called
- **THEN** the waveform animation timer SHALL be stopped

---
### Requirement: Microphone Toggle Button

The capsule SHALL include a microphone toggle button (QToolButton, 32x32 pixels) positioned to the right of the vertical separator. When the application is in the IDLE state, the button SHALL display a microphone icon. When the application is in any non-IDLE state (ACTIVATING, LISTENING, PROCESSING, INJECTING, ERROR), the button SHALL display a stop icon. Clicking the button in IDLE state SHALL invoke `CoreController.request_start()`. Clicking the button in any non-IDLE state SHALL invoke `CoreController.request_stop()`. The icons SHALL be rendered programmatically using QPainter (no external image resources).

#### Scenario: Start Recording via Button

- **WHEN** the application is in IDLE state and the user clicks the microphone button
- **THEN** the button SHALL invoke `CoreController.request_start()` and the icon SHALL change to a stop icon

#### Scenario: Stop Recording via Button

- **WHEN** the application is in LISTENING state and the user clicks the stop button
- **THEN** the button SHALL invoke `CoreController.request_stop()` and the icon SHALL change to a microphone icon after returning to IDLE

---
### Requirement: Device Dropdown Button

The capsule SHALL include a dropdown arrow button (QToolButton, 20x32 pixels) positioned immediately to the right of the microphone button. The button SHALL use `QToolButton.InstantPopup` mode with a QMenu listing all available audio input devices. The first menu item SHALL be "Default Microphone" with data value "default". Selecting a device from the menu SHALL update `config.voice.input_device`. The device list SHALL be populated using the existing `list_input_devices()` function from `device_selector.py`. CapsuleOverlay SHALL declare a `device_changed = Signal(str)` class-level signal. When the user selects a device from the dropdown menu, `_on_device_selected()` SHALL emit `device_changed` with the selected device name after updating config, enabling external components to react to the device change.

#### Scenario: Select Device from Dropdown

- **WHEN** the user clicks the dropdown arrow and selects a different microphone from the menu
- **THEN** the configuration `voice.input_device` SHALL be updated to the selected device name
- **THEN** CapsuleOverlay SHALL emit `device_changed` with the selected device name

#### Scenario: Default Device Option

- **WHEN** the user opens the device dropdown menu
- **THEN** the first item SHALL be "Default Microphone" with data value "default"


<!-- @trace
source: fix-device-switch
updated: 2026-03-08
code:
  - airtype/__main__.py
  - airtype/core/asr_engine.py
  - airtype/core/asr_qwen_vulkan.py
  - airtype/ui/settings_window.py
  - airtype/ui/settings_voice.py
  - locales/zh_CN.json
  - locales/zh_TW.json
  - airtype/core/asr_qwen_pytorch.py
  - airtype/core/asr_qwen_openvino.py
  - airtype/core/asr_sherpa.py
  - airtype/ui/overlay.py
  - airtype/core/asr_breeze.py
  - locales/en.json
  - airtype/ui/settings_dictionary.py
  - locales/ja.json
tests:
  - tests/test_asr_engine.py
  - tests/test_overlay.py
  - tests/test_asr_sherpa.py
-->

---
### Requirement: Vertical Separator

The capsule body SHALL include a vertical separator line (QFrame VLine, 1 pixel wide, 24 pixels tall) positioned between the waveform widget and the microphone button. The separator SHALL be rendered with semi-transparent white color (rgba 255, 255, 255, 0.3).

#### Scenario: Separator Visible Between Waveform and Controls

- **WHEN** the capsule is displayed
- **THEN** a vertical separator line SHALL be visible between the waveform area and the microphone button

---
### Requirement: Status Label Below Capsule

The capsule SHALL display the status text label below the capsule body (not inside it). The status label SHALL be centered horizontally, use 11px font size, and have a transparent background. The status label SHALL be hidden when the application is in IDLE state and SHALL be visible in all other states.

#### Scenario: Status Hidden in IDLE

- **WHEN** the application state is IDLE
- **THEN** the status label below the capsule SHALL NOT be visible

#### Scenario: Status Visible When Listening

- **WHEN** the application state transitions to LISTENING
- **THEN** the status label below the capsule SHALL be visible and display the localized listening text

---
### Requirement: CapsuleBody Separation

The capsule rounded-rectangle background SHALL be painted only on the CapsuleBody inner widget, not on the full CapsuleOverlay container. The CapsuleOverlay SHALL use a QVBoxLayout containing the CapsuleBody and the status label. The CapsuleBody SHALL have a fixed height of 48 pixels.

#### Scenario: Background Does Not Cover Status Label

- **WHEN** the capsule is displayed with status text visible
- **THEN** the rounded-rectangle background SHALL cover only the CapsuleBody area and SHALL NOT extend to the status label below