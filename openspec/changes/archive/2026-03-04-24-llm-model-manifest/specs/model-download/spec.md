## ADDED Requirements

### Requirement: Category-Filtered Model Listing

The `ModelManager` SHALL provide a `list_models_by_category(category: str)` method that returns all manifest entries whose `category` field matches the given value. Valid values are `"asr"` and `"llm"`.

#### Scenario: List ASR Models

- **WHEN** `list_models_by_category("asr")` is called
- **THEN** it SHALL return only manifest entries with `category="asr"`

#### Scenario: List LLM Models

- **WHEN** `list_models_by_category("llm")` is called
- **THEN** it SHALL return only manifest entries with `category="llm"`

#### Scenario: Unknown Category Returns Empty List

- **WHEN** `list_models_by_category("unknown")` is called
- **THEN** it SHALL return an empty list without raising an error
