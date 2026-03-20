## MODIFIED Requirements

### Requirement: Load Default Engine from Configuration

At startup, the system SHALL resolve the ASR engine to load by combining `voice.asr_model` (model name) and `voice.asr_inference_backend` (backend preference) configuration settings.

The resolution strategy SHALL follow this order:

1. If `voice.asr_model` directly matches a registered engine ID, the system SHALL use it as-is (backward compatibility).
2. If `voice.asr_model` matches a model name in the model-to-engine mapping, the system SHALL select an engine from the candidate list based on the `voice.asr_inference_backend` setting:
   - When backend is `"auto"`, the system SHALL iterate through the candidate engine list in priority order and select the first engine that is registered in the engine registry.
   - When backend is a specific value (e.g., `"openvino"`, `"vulkan"`, `"mlx"`), the system SHALL select the first candidate engine whose ID contains the backend string as a substring.
3. If no engine can be resolved, the system SHALL log a warning and remain with no active engine.

The `_MODEL_ENGINE_MAP` SHALL include `"qwen3-mlx"` in the candidate list for `"qwen3-asr-0.6b"`.

#### Scenario: Model Name Resolves to MLX Engine on Apple Silicon

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "auto"`, and only the engine `"qwen3-mlx"` is registered (macOS Apple Silicon)
- **THEN** the system SHALL resolve to `"qwen3-mlx"` and load it as the active engine

#### Scenario: Model Name Resolves via MLX Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "mlx"`
- **THEN** the system SHALL resolve to `"qwen3-mlx"` and load it as the active engine

#### Scenario: Model Name Resolves to Registered Engine via Auto Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "auto"`, and the engine `"qwen3-vulkan"` is registered but `"qwen3-openvino"` and `"qwen3-pytorch-cuda"` are not registered
- **THEN** the system SHALL resolve to `"qwen3-vulkan"` and load it as the active engine

#### Scenario: Model Name Resolves via Specific Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and `asr_inference_backend = "openvino"`, and the engine `"qwen3-openvino"` is registered
- **THEN** the system SHALL resolve to `"qwen3-openvino"` and load it as the active engine

#### Scenario: Direct Engine ID Still Works

- **WHEN** the configuration has `asr_model = "qwen3-vulkan"` (which is a registered engine ID)
- **THEN** the system SHALL load `"qwen3-vulkan"` directly without consulting the model-to-engine mapping

#### Scenario: Model Name With No Registered Backend

- **WHEN** the configuration has `asr_model = "qwen3-asr-0.6b"` and none of the candidate engines are registered
- **THEN** the system SHALL log a warning and remain with no active engine

#### Scenario: Configuration Specifies an Unknown Model

- **WHEN** the configuration has `asr_model = "nonexistent"` and it is neither a registered engine ID nor a known model name
- **THEN** the system SHALL log a warning and remain with no active engine
