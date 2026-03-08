# Spec: settings-voice

## Overview

Voice / ASR settings page within the Settings Panel. Provides audio input device selection, volume monitoring, noise suppression, ASR model selection, recognition language, recognition mode, and stream preview controls.

## Requirements

### Requirement: Voice Settings Page

The settings panel SHALL provide a Voice/ASR settings page containing: input device dropdown (dynamic), a refresh button, a volume slider with volume meter, noise suppression toggle, ASR model dropdown populated dynamically from the manifest (`category="asr"`), recognition language dropdown, recognition mode options (batch/stream), and stream preview toggle. The ASR model dropdown SHALL mark the hardware-recommended model with a "(建議)" label. The user's selection SHALL be persisted to `config.voice.asr_model`. The input device dropdown SHALL display a deduplicated list of physical input devices by delegating to the shared `list_input_devices()` utility; each physical device SHALL appear exactly once regardless of the number of Host APIs that expose it. The input device dropdown SHALL store the sounddevice device index (integer) as the item data value, NOT the device name string.

#### Scenario: Switch ASR Model

- **WHEN** the user selects "breeze-asr-25" from the ASR model dropdown
- **THEN** the config SHALL be updated (`voice.asr_model = "breeze-asr-25"`) and the ASR engine SHALL switch on the next recognition

#### Scenario: Hardware Recommendation Highlighted

- **WHEN** the ASR model dropdown is opened
- **THEN** the model recommended by `HardwareDetector.recommend()` SHALL be marked with "(建議)" in the dropdown list

#### Scenario: Test Microphone

- **WHEN** the user clicks the test button
- **THEN** the system SHALL record for 3 seconds using the device index from config, play back the recording, and SHALL display the volume level

#### Scenario: Device dropdown shows no duplicates

- **WHEN** the input device dropdown is opened on a system where the same physical microphone is exposed by multiple Host APIs
- **THEN** the dropdown SHALL list each physical device exactly once, showing the entry from the platform-preferred Host API

#### Scenario: Device selection stores index

- **WHEN** the user selects a specific input device from the dropdown
- **THEN** the config SHALL be updated with the integer device index (`config.voice.input_device = <int>`) and the `device_changed` signal SHALL emit the device index


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
### Requirement: Manifest-Driven ASR Model List

The ASR model dropdown SHALL be populated by calling `ModelManager.list_models_by_category("asr")` at settings page initialization. The dropdown SHALL display only models that are already downloaded locally (`ModelManager.is_downloaded()` returns `True`). Each entry SHALL display the model's `description` field as the label and use its `id` field as the value. If no models are downloaded, the dropdown SHALL display a placeholder text "(No downloaded models)" and SHALL be disabled. A hint label below the dropdown SHALL display a message directing the user to the Model Management page to download ASR models.

#### Scenario: Models Loaded from Manifest

- **WHEN** the Voice settings page is opened and downloaded ASR models exist
- **THEN** the ASR model dropdown SHALL contain only the downloaded entries returned by `list_models_by_category("asr")` with their description as the display label

#### Scenario: No Downloaded Models

- **WHEN** the Voice settings page is opened and no ASR models are downloaded
- **THEN** the dropdown SHALL display "(No downloaded models)" as a placeholder
- **THEN** the dropdown SHALL be disabled
- **THEN** a hint label SHALL be visible directing the user to the Model Management page

#### Scenario: Undownloaded Model Excluded

- **WHEN** a manifest ASR model is not present in the local model directory
- **THEN** the dropdown SHALL NOT include that model in the list