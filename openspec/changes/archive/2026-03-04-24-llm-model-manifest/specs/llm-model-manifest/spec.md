## ADDED Requirements

### Requirement: LLM Model Category Field

The manifest (`models/manifest.json`) SHALL include a `category` field on every model entry. Valid values are `"asr"` and `"llm"`. The `ModelManager` SHALL support filtering models by category.

#### Scenario: Filter LLM Models

- **WHEN** the caller requests models with `category="llm"`
- **THEN** the `ModelManager` SHALL return only entries whose `category` is `"llm"`

#### Scenario: Filter ASR Models

- **WHEN** the caller requests models with `category="asr"`
- **THEN** the `ModelManager` SHALL return only entries whose `category` is `"asr"`

### Requirement: Thinking Mode Declaration Fields

Each manifest model entry SHALL include `has_thinking_mode` (boolean) and `thinking_disable_token` (string or null) fields. These fields declare whether the model produces chain-of-thought tokens and how to suppress them.

#### Scenario: Model Without Thinking Mode

- **WHEN** a model entry has `has_thinking_mode: false`
- **THEN** `thinking_disable_token` SHALL be `null`

#### Scenario: Model With Thinking Mode and Disable Token

- **WHEN** a model entry has `has_thinking_mode: true`
- **THEN** `thinking_disable_token` SHALL be a non-empty string (e.g., `"/no_think"`) that, when prepended to the user prompt, suppresses chain-of-thought output

### Requirement: LLM GGUF Model Entries

The manifest SHALL include at least three LLM GGUF model entries covering small, medium, and large sizes to support the hardware recommendation decision tree.

#### Scenario: Small LLM Model Entry Present

- **WHEN** the manifest is loaded
- **THEN** it SHALL contain an entry with `id="qwen2.5-1.5b-instruct-q4_k_m"`, `category="llm"`, `has_thinking_mode=false`

#### Scenario: Medium LLM Model Entry Present

- **WHEN** the manifest is loaded
- **THEN** it SHALL contain an entry with `id="qwen2.5-3b-instruct-q4_k_m"`, `category="llm"`, `has_thinking_mode=false`

#### Scenario: Large LLM Model Entry Present

- **WHEN** the manifest is loaded
- **THEN** it SHALL contain an entry with `id="qwen2.5-7b-instruct-q4_k_m"`, `category="llm"`, `has_thinking_mode=false`

### Requirement: LLM Model Manifest Schema Backward Compatibility

Existing ASR model entries in the manifest SHALL be updated to include the `category`, `has_thinking_mode`, and `thinking_disable_token` fields so the schema is uniform across all entries.

#### Scenario: Existing ASR Entry Has Category Field

- **WHEN** the manifest is loaded
- **THEN** every existing ASR model entry SHALL have `category="asr"`, `has_thinking_mode=false`, and `thinking_disable_token=null`
