## ADDED Requirements

### Requirement: Hot Word Management

The system SHALL maintain a list of hot words with weights ranging from 1 to 10. Hot words SHALL be passed to the currently active ASR engine via `set_hot_words()` to increase recognition priority.

#### Scenario: Hot words applied to engine

- **WHEN** hot words ["PostgreSQL": 9, "鼎新": 8] are enabled
- **THEN** the ASR engine SHALL receive these hot words before recognition begins

### Requirement: Replacement Rules

The system SHALL apply post-ASR text replacement rules. Rules SHALL support both plain string matching and regular expression patterns. Rules SHALL be applied after ASR output and before LLM polishing.

#### Scenario: String replacement

- **WHEN** the rule "頂新" → "鼎新" is enabled and ASR outputs "頂新"
- **THEN** the output SHALL be replaced with "鼎新"

#### Scenario: Regular expression replacement

- **WHEN** a regular expression rule is enabled and matches the ASR output
- **THEN** the matched text SHALL be replaced according to the regular expression pattern

### Requirement: Dictionary Sets

The system SHALL support named dictionary sets stored as JSON files under `~/.airtype/dictionaries/`. Multiple dictionary sets SHALL be activatable simultaneously, with the union of all enabled sets applied.

#### Scenario: Switching dictionary sets

- **WHEN** the user enables the "ERP Terms" dictionary set
- **THEN** the hot words and replacement rules of that set SHALL be merged with those of all other enabled dictionary sets

### Requirement: Dictionary Engine as Pipeline Post-Processor

Dictionary replacement rules SHALL be applied as a post-processing step in the recognition pipeline, executed after ASR output and before LLM polishing.

#### Scenario: Dictionary processing order

- **WHEN** the ASR outputs text
- **THEN** dictionary replacement rules SHALL be applied first, before LLM polishing is performed (if enabled)
