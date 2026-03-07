## MODIFIED Requirements

### Requirement: Local LLM Inference via llama-cpp-python

The local engine SHALL use `llama_cpp.Llama` with a GGUF model, a context length of 4096 tokens, and a maximum generation length of `max(input_length × 3, 256)` tokens.

When `PolishEngine._get_local_engine()` initializes the `LocalLLMEngine`, it SHALL resolve the `llm.local_model` configuration value to an actual GGUF file path using the following strategy:

1. If the value is an existing file path, the system SHALL use it directly (backward compatibility).
2. Otherwise, the system SHALL read `models/manifest.json`, find the entry whose `id` matches the `llm.local_model` value, retrieve its `filename` field, and construct the full path as `~/.airtype/models/{filename}`.
3. If the model ID is not found in the manifest, the system SHALL raise a `PolishError` with a descriptive message including the unresolved model ID.

#### Scenario: Loading a local model by model ID

- **WHEN** the configuration has `llm.local_model = "qwen2.5-1.5b-instruct-q4_k_m"` and the manifest contains an entry with `id = "qwen2.5-1.5b-instruct-q4_k_m"` and `filename = "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"`
- **THEN** the system SHALL resolve the model path to `~/.airtype/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` and load it

#### Scenario: Loading a local model by direct file path

- **WHEN** the configuration has `llm.local_model = "/path/to/custom-model.gguf"` and the file exists
- **THEN** the system SHALL use the path directly without consulting the manifest

#### Scenario: Model ID not found in manifest

- **WHEN** the configuration has `llm.local_model = "nonexistent-model"` and no manifest entry matches
- **THEN** the system SHALL raise a `PolishError` with a message indicating the model ID cannot be resolved
