## Why

On Windows, `sounddevice.query_devices()` returns the same physical microphone multiple times — once per Host API (MME, DirectSound, WASAPI). The current device enumeration only filters by `max_input_channels > 0` without deduplication, causing the settings panel and internal device list to show 3–4 identical entries for a single microphone. Other audio applications show only one entry per physical device.

## What Changes

- `AudioCaptureService.list_devices()` and `list_input_devices()` now filter devices by the platform-preferred Host API (WASAPI on Windows, CoreAudio on macOS, ALSA/PulseAudio on Linux) before returning results.
- When the preferred Host API yields no devices, enumeration falls back to name-based deduplication (first-seen wins).
- `SettingsVoicePage._refresh_devices()` is refactored to use the shared `list_input_devices()` function instead of duplicating the query logic.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `audio-capture`: Device enumeration SHALL deduplicate results by preferring the platform-preferred Host API (WASAPI / CoreAudio / ALSA), falling back to name-based deduplication when no preferred API is available.
- `settings-voice`: Input device dropdown SHALL display only unique, deduplicated device names by delegating to the shared enumeration function.

## Impact

- Affected code:
  - `airtype/ui/device_selector.py` — `list_input_devices()` function
  - `airtype/ui/settings_voice.py` — `_refresh_devices()` method
  - `airtype/core/audio_capture.py` — `list_devices()` method
  - `tests/test_audio_capture.py` — update device enumeration tests
