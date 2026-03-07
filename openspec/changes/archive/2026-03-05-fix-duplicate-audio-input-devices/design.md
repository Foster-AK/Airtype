## Context

On Windows, `sounddevice` uses PortAudio which exposes each physical input device once per Host API (MME, DirectSound, WASAPI, WDM-KS). A single microphone therefore appears 3–4 times in the raw device list. The current enumeration filters only on `max_input_channels > 0`, which does not remove these duplicates. Three code sites duplicate this logic independently:

- `airtype/ui/device_selector.py` — `list_input_devices()`
- `airtype/ui/settings_voice.py` — `_refresh_devices()`
- `airtype/core/audio_capture.py` — `list_devices()`

## Goals / Non-Goals

**Goals:**

- Show each physical input device exactly once in the device dropdown and in `list_devices()` output.
- Use the highest-quality Host API available on each platform (WASAPI > DirectSound > MME on Windows; CoreAudio on macOS; PulseAudio > ALSA on Linux).
- Consolidate duplicate enumeration logic into a single shared function.

**Non-Goals:**

- Exposing individual Host-API–specific variants (advanced users who need a specific Host API are out of scope).
- Hot-plug detection or background device monitoring.
- Changes to audio stream opening (the device index still maps to the preferred-API entry).

## Decisions

### Preferred Host API Filtering with Name-Deduplication Fallback

Use `sd.query_hostapis()` to locate the preferred Host API index, then retain only devices belonging to that API. If no preferred API is found (non-standard PortAudio builds) or it yields zero input devices, fall back to name-based deduplication (keep first occurrence per unique name across all APIs).

**Rationale**: Filtering by Host API is the most semantically correct approach — WASAPI devices have lower latency and better exclusive-mode support than MME/DirectSound equivalents. Name deduplication as a fallback handles edge cases without breaking non-Windows platforms.

**Alternatives considered**:
- Name deduplication only: Simpler, but loses the ability to select the best-quality stream path.
- Always WASAPI-only (no fallback): Fails on macOS/Linux and on Windows machines where WASAPI is unavailable (very old drivers).

### Single Source of Truth in `device_selector.py`

Centralise the filtering+deduplication logic entirely within `list_input_devices()` in `airtype/ui/device_selector.py`. Both `settings_voice.py` (`_refresh_devices`) and `audio_capture.py` (`list_devices`) will delegate to this function.

**Rationale**: Eliminates three independent copies of the same logic. `device_selector.py` is already the public API for device listing in the UI layer. `audio_capture.py` returns typed `DeviceInfo` objects; it will call `list_input_devices()` and wrap results.

**Note**: `audio_capture.py` is a core module; importing from a UI module is acceptable here because `device_selector.py` contains no Qt code at the function level — `list_input_devices()` is a pure Python utility that only conditionally imports sounddevice. If this coupling becomes a concern in the future, the function can be moved to `airtype/utils/audio_devices.py`.

## Risks / Trade-offs

- **[Risk] WASAPI device index differs from MME index** → Each filtered device retains its original sounddevice index; `sd.InputStream(device=<index>)` will open the WASAPI entry correctly. No index remapping needed.
- **[Risk] Preferred-API name string varies by PortAudio version** → The keyword match is case-insensitive substring (`"wasapi" in api["name"].lower()`), not an exact match, which tolerates minor naming variations.
- **[Risk] Importing `device_selector` from `audio_capture`** → If the UI layer gains heavy Qt imports in future, this import will pull them into the core. Mitigation: keep `list_input_devices()` free of Qt imports (it already is).

## Migration Plan

No schema changes. No user-visible config migration required. The stored `config.voice.input_device` value is a device name string; if the user previously selected a duplicate entry, the name still matches the deduplicated entry. Existing unit tests that mock `query_devices` must be updated to also mock `query_hostapis`.

## Open Questions

(none)
