## ADDED Requirements

### Requirement: Thinking Mode Token Suppression

When loading a local GGUF model, the `LocalLLMEngine` (or `PolishEngine`) SHALL read the model's manifest entry to check `has_thinking_mode`. If `has_thinking_mode` is `true`, the engine SHALL prepend `thinking_disable_token` to the user prompt before inference to suppress chain-of-thought output. If `has_thinking_mode` is `false` or the manifest entry cannot be found, no token is prepended and inference proceeds normally.

#### Scenario: Model Without Thinking Mode

- **WHEN** the loaded model has `has_thinking_mode: false` in the manifest
- **THEN** the prompt SHALL be passed to the model unchanged (no token prepended)

#### Scenario: Model With Thinking Mode and Disable Token

- **WHEN** the loaded model has `has_thinking_mode: true` and a non-null `thinking_disable_token` (e.g., `"/no_think"`)
- **THEN** the engine SHALL prepend `thinking_disable_token` to the prompt string before calling `llama_cpp.Llama`

#### Scenario: Manifest Entry Not Found

- **WHEN** no manifest entry exists for the current model id
- **THEN** the engine SHALL proceed without prepending any token and SHALL log a debug-level warning
