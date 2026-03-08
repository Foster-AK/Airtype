## MODIFIED Requirements

### Requirement: Audio Stream Capture

The system SHALL capture audio from the selected input device at 16000 Hz sample rate, 16-bit PCM or float32 format, mono channel, with a buffer size of 512 samples (32 ms per frame). When `AudioCaptureService.start()` receives an integer device index that does not correspond to a valid input device, the system SHALL fall back to the system default input device and log a warning. On Windows, the system SHALL pass `sd.WasapiSettings(auto_convert=True)` as `extra_settings` to `sd.InputStream` to enable OS-level sample rate conversion for devices that do not natively support 16 kHz. If `WasapiSettings` construction fails (e.g., non-WASAPI Host API), the system SHALL fall back to `extra_settings=None`. On non-Windows platforms, `extra_settings` SHALL be `None`.

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

#### Scenario: WASAPI auto_convert on Windows

- **WHEN** `AudioCaptureService.start()` is called on a Windows system
- **THEN** the `sd.InputStream` SHALL be created with `extra_settings=sd.WasapiSettings(auto_convert=True)`

#### Scenario: WASAPI auto_convert fallback on non-WASAPI Host API

- **WHEN** `AudioCaptureService.start()` is called on Windows but `sd.WasapiSettings` construction raises an exception
- **THEN** the system SHALL fall back to `extra_settings=None` and proceed normally

#### Scenario: Non-Windows platform

- **WHEN** `AudioCaptureService.start()` is called on a non-Windows platform (macOS or Linux)
- **THEN** the `sd.InputStream` SHALL be created with `extra_settings=None`

#### Scenario: Fallback path uses WASAPI auto_convert

- **WHEN** an integer device index fails to open and the system falls back to the default device on Windows
- **THEN** the fallback `sd.InputStream` SHALL also use `extra_settings=sd.WasapiSettings(auto_convert=True)`
