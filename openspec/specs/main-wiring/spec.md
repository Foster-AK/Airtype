# main-wiring Specification

## Purpose

TBD - created by archiving change '23-main-wiring'. Update Purpose after archive.

## Requirements

### Requirement: Application Entry Point Component Wiring

The application entry point (`__main__.py`) SHALL create and connect all core components in the following order: i18n initialization, AudioCaptureService, VadEngine, ASREngineRegistry (with engine registration), FocusManager, TextInjector, DictionaryEngine, PolishEngine, BatchRecognitionPipeline, HotkeyManager, CoreController (with all dependencies injected), and UI components (CapsuleOverlay, SettingsWindow, SystemTrayIcon). After DictionaryEngine is successfully initialized and an ASR engine is loaded, the entry point SHALL call `dictionary_engine.sync_hot_words(asr_engine)` to inject active hot words into the ASR engine.

#### Scenario: Full Component Chain Initialization

- **WHEN** the application starts via `python -m airtype`
- **THEN** all core components SHALL be created and connected in dependency order
- **THEN** CoreController SHALL receive pipeline, text_injector, polish_engine, and dictionary_engine parameters

#### Scenario: Application Starts Without Crash

- **WHEN** the application starts with all dependencies installed and models downloaded
- **THEN** the application SHALL enter the Qt event loop without errors

#### Scenario: Hot Words Injected at Startup

- **WHEN** the application starts with a DictionaryEngine containing enabled hot words and an active ASR engine
- **THEN** `sync_hot_words(asr_engine)` SHALL be called after DictionaryEngine initialization
- **THEN** the ASR engine SHALL receive all enabled hot words from active dictionary sets

#### Scenario: Hot Words Skipped When No ASR Engine

- **WHEN** the application starts but no ASR engine is available (asr_engine is None)
- **THEN** `sync_hot_words()` SHALL NOT be called
- **THEN** no error SHALL be raised


<!-- @trace
source: fix-hot-words
updated: 2026-03-07
code:
  - airtype/core/asr_breeze.py
  - airtype/ui/settings_window.py
  - airtype/core/asr_qwen_pytorch.py
  - airtype/core/asr_qwen_openvino.py
  - airtype/__main__.py
  - locales/zh_TW.json
  - locales/zh_CN.json
  - airtype/ui/settings_dictionary.py
  - locales/en.json
  - airtype/core/asr_qwen_vulkan.py
  - airtype/core/asr_engine.py
  - locales/ja.json
  - airtype/core/asr_sherpa.py
tests:
  - tests/test_asr_sherpa.py
  - tests/test_asr_engine.py
-->

---
### Requirement: Graceful Degradation on Component Failure

Each component initialization SHALL be wrapped in error handling. If a non-critical component fails to initialize, the application SHALL continue with degraded functionality rather than crashing.

#### Scenario: No Microphone Available

- **WHEN** AudioCaptureService fails to start (no microphone)
- **THEN** audio_capture SHALL be None
- **THEN** BatchRecognitionPipeline SHALL NOT be created
- **THEN** the UI SHALL display normally without voice recognition capability

#### Scenario: No ASR Model Downloaded

- **WHEN** no ASR engine can be loaded (models not downloaded)
- **THEN** asr_engine SHALL be None
- **THEN** BatchRecognitionPipeline SHALL NOT be created
- **THEN** the UI SHALL display normally without voice recognition capability

#### Scenario: Optional Engine Failure

- **WHEN** DictionaryEngine or PolishEngine fails to initialize
- **THEN** the corresponding engine SHALL be None
- **THEN** CoreController SHALL skip dictionary post-processing or LLM polishing respectively

---
### Requirement: ASR Engine Dynamic Registration

The entry point SHALL dynamically import and register all available ASR engine modules (asr_qwen_openvino, asr_qwen_pytorch, asr_qwen_vulkan, asr_sherpa, asr_breeze) by calling each module's `register(registry)` function. Import failures SHALL be silently logged and skipped.

#### Scenario: Partial Engine Availability

- **WHEN** only sherpa-onnx is installed but OpenVINO is not
- **THEN** the sherpa engine SHALL be registered successfully
- **THEN** the OpenVINO engine import failure SHALL be logged at DEBUG level
- **THEN** ASREngineRegistry SHALL load the default engine from config

---
### Requirement: RMS Polling for Waveform Animation

The entry point SHALL create a QTimer with 33ms interval that polls AudioCaptureService.rms and calls CapsuleOverlay.update_rms() to drive the waveform animation.

#### Scenario: Waveform Reflects Speech

- **WHEN** the user speaks into the microphone during LISTENING state
- **THEN** the waveform bars SHALL animate proportionally to the audio RMS value

#### Scenario: No Audio Capture Available

- **WHEN** AudioCaptureService is None (initialization failed)
- **THEN** the RMS polling timer SHALL NOT be created
- **THEN** the waveform SHALL remain at minimum height

---
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
### Requirement: I18n Language Initialization

The entry point SHALL call `set_language(cfg.general.language)` before creating UI components to ensure the correct language is applied.

#### Scenario: Language Setting Applied

- **WHEN** config.general.language is set to "en"
- **THEN** all UI text SHALL be displayed in English

---
### Requirement: Settings Window Integration

The entry point SHALL pass dictionary_engine to SettingsWindow constructor and SHALL call connect_rms_feed() to enable the voice settings page volume meter.

#### Scenario: Dictionary Settings Page Functional

- **WHEN** the user opens the dictionary settings page
- **THEN** the dictionary engine SHALL be available for editing hot words and replacement rules

---
### Requirement: Resource Cleanup Order

On application exit, resources SHALL be cleaned up in reverse initialization order: RMS timer stop, AudioCaptureService stop, ASREngineRegistry shutdown, CoreController shutdown.

#### Scenario: Clean Shutdown

- **WHEN** the user quits the application
- **THEN** all resources SHALL be released without errors
- **THEN** no audio device handles SHALL remain open