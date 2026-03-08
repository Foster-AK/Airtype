## MODIFIED Requirements

### Requirement: Audio Stream Capture

The system SHALL capture audio from the selected input device at 16000 Hz sample rate, 16-bit PCM or float32 format, mono channel, with a buffer size of 512 samples (32 ms per frame). When `AudioCaptureService.start()` receives an integer device index that does not correspond to a valid input device, the system SHALL fall back to the system default input device and log a warning.

#### Scenario: Start capture with default device

- **WHEN** `AudioCaptureService.start()` is called with device set to `"default"`
- **THEN** the system SHALL begin capturing audio from the system default input device without error

#### Scenario: Start capture with specified device

- **WHEN** `AudioCaptureService.start()` is called with a specific device index (integer)
- **THEN** the system SHALL begin capturing audio from that device

#### Scenario: Start capture with invalid device index

- **WHEN** `AudioCaptureService.start()` is called with an integer device index that does not correspond to a valid input device
- **THEN** the system SHALL log a warning and fall back to capturing from the system default input device

#### Scenario: Stop capture

- **WHEN** `AudioCaptureService.stop()` is called while capturing
- **THEN** the system SHALL stop the audio stream and release the device
