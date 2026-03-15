## MODIFIED Requirements

### Requirement: Application Entry Point Component Wiring

The application entry point (`__main__.py`) SHALL create and connect all core components in the following order: i18n initialization, AudioCaptureService, VadEngine, ASREngineRegistry (with engine registration), FocusManager, TextInjector, DictionaryEngine, PolishEngine, BatchRecognitionPipeline, HotkeyManager, CoreController (with all dependencies injected), and UI components (CapsuleOverlay, SettingsWindow, SystemTrayIcon). After DictionaryEngine is successfully initialized and an ASR engine is loaded, the entry point SHALL call `dictionary_engine.sync_hot_words(asr_engine)` to inject active hot words into the ASR engine.

The engine module list (`_ENGINE_MODULE_MAP`) SHALL include `"airtype.core.asr_qwen_mlx"` as a candidate module for MLX-based Qwen3-ASR inference on macOS Apple Silicon.

#### Scenario: Full Component Chain Initialization

- **WHEN** the application starts via `python -m airtype`
- **THEN** all core components SHALL be created and connected in dependency order
- **THEN** CoreController SHALL receive pipeline, text_injector, polish_engine, and dictionary_engine parameters

#### Scenario: MLX Engine Module Loaded on macOS

- **WHEN** the application starts on macOS Apple Silicon with `mlx` installed
- **THEN** `airtype.core.asr_qwen_mlx` SHALL be imported and `register()` SHALL add `"qwen3-mlx"` to the registry

#### Scenario: MLX Engine Module Skipped on Non-macOS

- **WHEN** the application starts on Windows or Linux
- **THEN** `airtype.core.asr_qwen_mlx` import SHALL fail gracefully and log a debug message

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
