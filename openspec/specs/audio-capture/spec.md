# Audio Capture Spec

## Purpose

This capability defines how Airtype captures real-time audio input from the host system. It covers device enumeration, streaming capture, ring-buffer management, RMS volume computation, and thread-safe data exchange between the audio callback thread and consumer threads.

---

## Requirements

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


<!-- @trace
source: fix-device-name-collision
updated: 2026-03-08
code:
  - airtype/core/asr_qwen_pytorch.py
  - airtype/ui/settings_voice.py
  - airtype/ui/settings_dictionary.py
  - locales/en.json
  - locales/zh_TW.json
  - airtype/core/audio_capture.py
  - airtype/core/asr_qwen_vulkan.py
  - locales/zh_CN.json
  - airtype/ui/overlay.py
  - airtype/core/asr_engine.py
  - airtype/core/asr_sherpa.py
  - airtype/ui/settings_window.py
  - airtype/config.py
  - airtype/ui/device_selector.py
  - locales/ja.json
  - airtype/core/asr_qwen_openvino.py
  - airtype/__main__.py
  - airtype/core/asr_breeze.py
tests:
  - tests/test_config.py
  - tests/test_audio_capture.py
  - tests/test_asr_engine.py
  - tests/test_settings_window.py
  - tests/test_asr_sherpa.py
  - tests/test_overlay.py
-->

---
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

---
### Requirement: Runtime Device Switching

The system SHALL support switching the active input device at runtime without restarting the application. The switch SHALL stop the current stream and start a new stream on the selected device.

#### Scenario: Switch device during capture

- **WHEN** `AudioCaptureService.set_device(new_index)` is called while audio capture is active
- **THEN** the system SHALL stop the current stream, start a new stream on the new device, and resume capture within 200 ms

---
### Requirement: Audio Data Ring Buffer

The system SHALL maintain a circular ring buffer of 3 seconds (48000 samples at 16 kHz) using a numpy array. When the buffer is full, new audio frames SHALL overwrite the oldest data.

#### Scenario: Buffer accumulation

- **WHEN** audio frames are captured continuously for 3 seconds
- **THEN** the ring buffer SHALL contain exactly 3 seconds of the most recent audio data

#### Scenario: Buffer overflow

- **WHEN** audio capture continues beyond 3 seconds without consumption
- **THEN** the oldest samples SHALL be overwritten by new samples

---
### Requirement: RMS Volume Calculation

The system SHALL compute the RMS (root mean square) volume of each audio frame (512 samples) and make it available to consumers for waveform visualization.

#### Scenario: RMS output during speech

- **WHEN** the user speaks into the microphone
- **THEN** the RMS value SHALL be greater than the RMS value during silence

#### Scenario: RMS output during silence

- **WHEN** there is no audio input (silence)
- **THEN** the RMS value SHALL be close to zero

---
### Requirement: Thread-Safe Data Exchange

Audio frames captured in the callback thread SHALL be passed to consumer threads via a thread-safe `queue.Queue`. The callback SHALL NOT perform blocking operations.

#### Scenario: Consumer reads audio frame

- **WHEN** a consumer calls `get_frame()` on the audio queue
- **THEN** it SHALL receive the next available audio frame in FIFO order