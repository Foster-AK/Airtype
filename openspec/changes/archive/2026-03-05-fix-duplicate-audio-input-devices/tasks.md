## 1. Core Logic — Preferred Host API Filtering with Name-Deduplication Fallback

- [x] 1.1 Update `list_input_devices()` in `airtype/ui/device_selector.py` to implement Single Source of Truth in `device_selector.py`: add `sd.query_hostapis()` call, resolve platform-preferred Host API index (WASAPI / CoreAudio / PulseAudio/ALSA) implementing Preferred Host API Filtering with Name-Deduplication Fallback, filter candidates by that index, and fall back to name-deduplication (first-occurrence) when preferred API yields no results

## 2. Consumers — Input Device Enumeration Delegation

- [x] 2.1 [P] Update `AudioCaptureService.list_devices()` in `airtype/core/audio_capture.py` to call `list_input_devices()` from `device_selector` and wrap results into `DeviceInfo` objects, satisfying the Input Device Enumeration requirement
- [x] 2.2 [P] Refactor `_refresh_devices()` in `airtype/ui/settings_voice.py` to call `list_input_devices()` instead of inline `query_devices`, satisfying the Voice Settings Page device dropdown deduplication requirement; preserve `str(d["index"])` as itemData

## 3. Tests

- [x] 3.1 [P] Update `tests/test_audio_capture.py`: add `query_hostapis` mock to existing device enumeration tests; add test case that verifies `list_devices()` returns one entry when the same device name appears under multiple Host APIs (Input Device Enumeration — preferred API unavailable scenario)
- [x] 3.2 [P] Add unit tests in `tests/test_device_selector.py` (new file): test `list_input_devices()` with mocked `query_devices` + `query_hostapis`; cover WASAPI-preferred path, fallback deduplication path, and empty-device path

## 4. Verification

- [x] 4.1 Run `python -m pytest tests/test_audio_capture.py tests/test_device_selector.py -v` and confirm all tests pass
- [x] 4.2 Launch the application and open Settings → Voice/ASR → confirm the input device dropdown lists each physical device exactly once with no duplicates (Voice Settings Page — Device dropdown shows no duplicates)
