## ADDED Requirements

### Requirement: Breeze-ASR-25 Batch Recognition

The system SHALL implement `BreezeAsrEngine` to load Breeze-ASR-25 via faster-whisper (preferred) or HuggingFace Transformers pipeline. The engine SHALL conform to the ASREngine Protocol.

#### Scenario: Recognize Taiwanese Mandarin

- **WHEN** Taiwanese Mandarin speech is processed with Breeze-ASR-25
- **THEN** recognition accuracy SHALL exceed that of standard Whisper for Taiwan-specific vocabulary

#### Scenario: Prefer faster-whisper over HuggingFace

- **WHEN** both faster-whisper and transformers are installed
- **THEN** the engine SHALL use faster-whisper (CTranslate2) for better performance

### Requirement: Breeze Code-Switching Support

The engine SHALL support code-switching between Mandarin Chinese and English within a single utterance without requiring manual language switching.

#### Scenario: Mixed-language utterance

- **WHEN** the user says "請幫我 check 一下 database"
- **THEN** the result SHALL correctly contain both Chinese and English text

### Requirement: Breeze Engine Registration

The engine SHALL register as `"breeze-asr-25"` in the `ASREngineRegistry` when faster-whisper or transformers is available.

#### Scenario: Register when available

- **WHEN** the faster-whisper or transformers package is installed
- **THEN** `"breeze-asr-25"` SHALL be available in the engine registry
