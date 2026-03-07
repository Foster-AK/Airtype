## MODIFIED Requirements

### Requirement: Input Device Enumeration

The system SHALL enumerate audio input devices and return a deduplicated list of device names and indices. The implementation SHALL use `sounddevice.query_hostapis()` to identify the platform-preferred Host API (WASAPI on Windows, CoreAudio on macOS, PulseAudio or ALSA on Linux) and return only the devices belonging to that Host API. If no preferred Host API is found or it yields zero input devices, the implementation SHALL fall back to returning all devices with `max_input_channels > 0`, deduplicated by name (first occurrence wins). The implementation SHALL use `sounddevice.query_devices()` (without a `kind` parameter) as the base device list.

#### Scenario: List devices on Windows with WASAPI available

- **WHEN** `AudioCaptureService.list_devices()` is called on a Windows system where WASAPI is available
- **THEN** the system SHALL return only input devices belonging to the WASAPI Host API, with no duplicate names

#### Scenario: List devices — preferred API unavailable

- **WHEN** `AudioCaptureService.list_devices()` is called and no platform-preferred Host API is found
- **THEN** the system SHALL return all input devices with `max_input_channels > 0`, deduplicated by name (first occurrence per unique name)

#### Scenario: No input devices available

- **WHEN** no audio input devices are available on the system
- **THEN** the system SHALL return an empty list and log a warning
