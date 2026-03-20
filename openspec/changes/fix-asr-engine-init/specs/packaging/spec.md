## MODIFIED Requirements

### Requirement: Single Executable via PyInstaller

The system SHALL use PyInstaller as the primary build tool to produce a single executable. The executable SHALL bundle all Python dependencies and embedded model files. The PyInstaller spec SHALL include all dynamically loaded ASR engine modules in `hiddenimports` to ensure they are packaged into the executable.

#### Scenario: Build Executable

- **WHEN** the build script is executed
- **THEN** a single executable SHALL be produced that runs without requiring a Python installation

#### Scenario: Dynamically Loaded ASR Engine Modules Included

- **WHEN** the PyInstaller spec is used to build the application
- **THEN** all ASR engine modules loaded via `importlib.import_module()` SHALL be listed in `hiddenimports`
- **THEN** the built executable SHALL contain `airtype.core.asr_qwen_onnx`, `airtype.core.asr_qwen_pytorch`, `airtype.core.asr_qwen_vulkan`, `airtype.core.asr_qwen_mlx`, `airtype.core.asr_sherpa`, `airtype.core.asr_breeze`, `airtype.core.asr_engine`, `airtype.core.asr_utils`, and `airtype.core.processor_numpy`

#### Scenario: Engine Module Registration in Packaged App

- **WHEN** the packaged application starts on macOS with onnxruntime installed
- **THEN** `airtype.core.asr_qwen_onnx` SHALL be importable and its `register()` function SHALL succeed
