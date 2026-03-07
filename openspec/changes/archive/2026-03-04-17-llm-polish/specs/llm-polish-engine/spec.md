## ADDED Requirements

### Requirement: Local LLM Polishing

The system SHALL support local text polishing using llama-cpp-python with GGUF model files. The engine SHALL support three polishing modes: light (punctuation only), medium (punctuation and fluency), and full (punctuation, fluency, and grammar).

#### Scenario: Light mode punctuation

- **WHEN** ASR output "你好世界今天天氣很好" is polished in light mode
- **THEN** the result SHALL contain punctuation marks: "你好，世界。今天天氣很好。"

#### Scenario: 3-second timeout

- **WHEN** LLM inference takes longer than 3 seconds
- **THEN** the system SHALL return the original unpolished text

### Requirement: Polishing Modes Implemented via Prompt Template Variants

A distinct prompt template SHALL be defined for each of the three modes: light, medium, and full. The user SHALL be able to override the prompt via `llm.custom_prompt` in the config.

#### Scenario: Custom prompt

- **WHEN** a custom_prompt is set in the config
- **THEN** the system SHALL use the custom prompt instead of the built-in template

### Requirement: Local LLM Inference via llama-cpp-python

The local engine SHALL use `llama_cpp.Llama` with a GGUF model, a context length of 4096 tokens, and a maximum generation length of `max(input_length × 3, 256)` tokens.

#### Scenario: Loading a local model

- **WHEN** a valid GGUF model path is configured
- **THEN** the system SHALL load the model and be ready for polishing

### Requirement: Model Size Auto-Downgrade

The engine SHALL accept a `model_size_b` float parameter (model size in billions). If the requested polishing mode exceeds the model's capability threshold, the engine SHALL silently downgrade to the highest supported mode and log the downgrade event at INFO level.

Mode capability thresholds: LIGHT requires 0B+, MEDIUM requires 1.5B+, FULL requires 3.0B+.

#### Scenario: Auto-downgrade FULL to MEDIUM

- **WHEN** a 1.5B model is loaded and FULL mode is requested
- **THEN** the engine SHALL apply MEDIUM mode and log the downgrade at INFO level

#### Scenario: Auto-downgrade to LIGHT

- **WHEN** a 0.5B model is loaded and MEDIUM mode is requested
- **THEN** the engine SHALL apply LIGHT mode and log the downgrade at INFO level

### Requirement: ASR Output Pre-cleaning

Before calling the LLM, the engine SHALL apply pre-cleaning to the input text: collapsing repeated filler characters (e.g., 嗯嗯嗯 → 嗯), collapsing repeated filler phrases (e.g., 然後然後 → 然後), and removing extra whitespace.

#### Scenario: Pre-clean repeated fillers

- **WHEN** input contains "嗯嗯嗯啊" or "然後然後然後"
- **THEN** pre-clean SHALL produce "嗯啊" and "然後" respectively

### Requirement: LLM Output Post-cleaning

After receiving LLM output, the engine SHALL apply post-cleaning: removing common small-model preamble prefixes (e.g., "好的，", "以下是...：", "輸出："), removing markdown code-block wrappers, and removing surrounding quotation marks (half-width `"..."` or full-width `「...」`).

#### Scenario: Post-clean preamble prefix

- **WHEN** LLM returns "好的，以下是結果：今天開會，主管說要導入新系統。"
- **THEN** post-clean SHALL return "今天開會，主管說要導入新系統。"

### Requirement: Few-shot Prompt Templates

Each of the three mode prompts SHALL include one concrete input→output example to guide small-model pattern matching. The example SHALL use realistic Traditional Chinese ASR output. Each prompt SHALL end with the instruction "直接輸出結果，不要加任何說明。" as the final line.

#### Scenario: Few-shot example in light mode prompt

- **WHEN** the LIGHT mode system prompt is used
- **THEN** it SHALL contain an example showing punctuation-only transformation (no word changes)

### Requirement: Sampling Parameters Configuration

The local engine SHALL use fixed sampling parameters for deterministic polishing: `temperature=0.1`, `top_p=0.8`, `top_k=20`, `min_p=0.0`, `repeat_penalty=1.1`.

#### Scenario: Deterministic output

- **WHEN** the same input is polished twice in LIGHT mode
- **THEN** the results SHALL be identical (given identical model and parameters)
