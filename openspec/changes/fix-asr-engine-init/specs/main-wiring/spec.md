## MODIFIED Requirements

### Requirement: Application Entry Point Component Wiring

The application entry point (`__main__.py`) SHALL create and connect all core components in the following order: i18n initialization, AudioCaptureService, VadEngine, ASREngineRegistry (with engine registration), FocusManager, TextInjector, DictionaryEngine, PolishEngine, BatchRecognitionPipeline, HotkeyManager, CoreController (with all dependencies injected), and UI components (CapsuleOverlay, SettingsWindow, SystemTrayIcon). After DictionaryEngine is successfully initialized and an ASR engine is loaded, the entry point SHALL call `dictionary_engine.sync_hot_words(asr_engine)` to inject active hot words into the ASR engine.

The engine module list (`_ENGINE_MODULE_MAP`) SHALL include `"airtype.core.asr_qwen_mlx"` as a candidate module for MLX-based Qwen3-ASR inference on macOS Apple Silicon.

Engine module registration failures SHALL be logged at WARNING level. After `load_default_engine()` completes, the entry point SHALL check `asr_registry.active_engine` to determine whether an engine was successfully loaded, and SHALL log the result at the appropriate level (INFO for success with engine ID, WARNING for failure with list of registered engine IDs).

Before calling `load_default_engine()`, the entry point SHALL validate model file integrity using `ModelManager.validate_model_files()` when the configured model is marked as downloaded and the engine factory provides a `REQUIRED_FILES` attribute. Validation results SHALL be stored for use in the ASR warning dialog.

#### Scenario: Full Component Chain Initialization

- **WHEN** the application starts via `python -m airtype`
- **THEN** all core components SHALL be created and connected in dependency order
- **THEN** CoreController SHALL receive pipeline, text_injector, polish_engine, and dictionary_engine parameters

#### Scenario: MLX Engine Module Loaded on macOS

- **WHEN** the application starts on macOS Apple Silicon with `mlx` installed
- **THEN** `airtype.core.asr_qwen_mlx` SHALL be imported and `register()` SHALL add `"qwen3-mlx"` to the registry

#### Scenario: MLX Engine Module Skipped on Non-macOS

- **WHEN** the application starts on Windows or Linux
- **THEN** `airtype.core.asr_qwen_mlx` import SHALL fail gracefully and log a warning message

#### Scenario: Application Starts Without Crash

- **WHEN** the application starts with all dependencies installed and models downloaded
- **THEN** the application SHALL enter the Qt event loop without errors

#### Scenario: Hot Words Injected at Startup

- **WHEN** the application starts with a DictionaryEngine containing enabled hot words and an active ASR engine
- **THEN** `sync_hot_words(asr_engine)` SHALL be called after DictionaryEngine initialization
- **THEN** the ASR engine SHALL receive all enabled hot words from active dictionary sets

#### Scenario: Hot Words Skipped When No ASR Engine

- **WHEN** the application starts but no ASR engine is available
- **THEN** hot word synchronization SHALL be skipped without error

#### Scenario: Engine Registration Failure Logged at Warning Level

- **WHEN** an ASR engine module fails to import or register during startup
- **THEN** the failure SHALL be logged at WARNING level with the module path and exception details

#### Scenario: ASR Engine Load Success Accurately Reported

- **WHEN** `load_default_engine()` completes and `active_engine` is not None
- **THEN** the entry point SHALL log at INFO level with the active engine ID

#### Scenario: ASR Engine Load Failure Accurately Reported

- **WHEN** `load_default_engine()` completes and `active_engine` is None
- **THEN** the entry point SHALL log at WARNING level with the list of registered engine IDs

#### Scenario: Model Integrity Pre-check Detects Incomplete Download

- **WHEN** the configured ASR model directory exists but is missing required files
- **THEN** the entry point SHALL log a WARNING with the list of missing files
- **THEN** the validation result SHALL be stored for the ASR warning dialog

### Requirement: Graceful Degradation on Component Failure

Each component initialization SHALL be wrapped in error handling. If a non-critical component fails to initialize, the application SHALL continue with degraded functionality rather than crashing. When `asr_engine` is None, the ASR warning dialog SHALL distinguish between "model not downloaded" and "model files incomplete" based on model integrity validation results. If model files are incomplete, the dialog SHALL display the specific missing files and recommend re-downloading.

#### Scenario: No Microphone Available

- **WHEN** AudioCaptureService fails to start due to no microphone
- **THEN** audio_capture SHALL be set to None and the application SHALL continue without audio

#### Scenario: ASR Warning Dialog Shows Incomplete Model Details

- **WHEN** `asr_engine` is None and model integrity validation detected missing files
- **THEN** the warning dialog SHALL display the specific missing file names
- **THEN** the dialog SHALL recommend deleting and re-downloading the model

#### Scenario: ASR Warning Dialog Shows No Model Downloaded

- **WHEN** `asr_engine` is None and no model is downloaded
- **THEN** the warning dialog SHALL instruct the user to download a model from Settings
