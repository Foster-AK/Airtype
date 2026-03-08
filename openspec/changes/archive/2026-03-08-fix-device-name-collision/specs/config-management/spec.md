## MODIFIED Requirements

### Requirement: 設定資料模型

The system SHALL provide a typed configuration model using Python `@dataclass` classes corresponding to the JSON schema defined in PRD §7.4. The model SHALL contain the following sections: `GeneralConfig`, `VoiceConfig`, `LlmConfig`, `DictionaryConfig`, `AppearanceConfig`, `ShortcutsConfig`, composed into a top-level `AirtypeConfig`. The `VoiceConfig.input_device` field SHALL accept either the string `"default"` (for system default device) or an integer device index. The JSON serialization SHALL preserve the value type (string or integer) without conversion.

#### Scenario: Default config values

- **WHEN** `AirtypeConfig` is instantiated with no arguments
- **THEN** all fields SHALL have default values conforming to PRD §7.4 (e.g., `general.language = "zh-TW"`, `general.silence_timeout = 1.5`, `voice.asr_model = "qwen3-asr-0.6b"`, `voice.input_device = "default"`, `appearance.theme = "system"`)

#### Scenario: Config serialization round-trip

- **WHEN** an `AirtypeConfig` is serialized to JSON and deserialized back
- **THEN** the resulting object SHALL be equal to the original object

#### Scenario: Integer device index round-trip

- **WHEN** `VoiceConfig.input_device` is set to an integer value (e.g., `41`) and serialized to JSON then deserialized
- **THEN** the deserialized `input_device` value SHALL be the integer `41`, not the string `"41"`
