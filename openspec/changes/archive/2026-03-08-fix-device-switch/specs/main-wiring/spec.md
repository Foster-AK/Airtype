## MODIFIED Requirements

### Requirement: Device Selector Wiring

The entry point SHALL connect CapsuleOverlay's `device_changed` Signal to `AudioCaptureService.set_device()` so that device switching from the capsule takes effect immediately. The entry point SHALL also connect SettingsVoicePage's `device_changed` Signal to `AudioCaptureService.set_device()` so that device switching from the settings window takes effect immediately. Both connections SHALL be established only when AudioCaptureService is available (not None).

#### Scenario: Switch Device from Capsule

- **WHEN** the user selects a different microphone from the capsule device dropdown
- **THEN** AudioCaptureService SHALL switch to the selected device

#### Scenario: Switch Device from Settings Window

- **WHEN** the user selects a different microphone from the settings voice page device combo
- **THEN** AudioCaptureService SHALL switch to the selected device

#### Scenario: No Audio Capture Available

- **WHEN** AudioCaptureService is None (initialization failed)
- **THEN** no device change Signal connections SHALL be established
- **THEN** no error SHALL be raised
