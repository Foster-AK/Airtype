# llm-pipeline-integration Specification

## Purpose

Defines how `CoreController` integrates the `PolishEngine` into the recognition-to-injection pipeline, including optional preview dialog interaction and graceful fallback on polish failure.

## Requirements

### Requirement: LLM Polish Integration in Recognition Pipeline

When LLM polishing is enabled, `CoreController` SHALL apply `PolishEngine.polish()` to the ASR recognition result before text injection. If polishing raises an exception or times out, the controller SHALL silently fall back to the original text and continue injection without entering an error state.

#### Scenario: Polish disabled — inject original text

- **WHEN** `config.llm.enabled` is `False`
- **THEN** the controller SHALL inject the original ASR text without calling `PolishEngine`

#### Scenario: Polish enabled, no preview — inject polished text

- **WHEN** `config.llm.enabled` is `True` and `config.llm.preview_before_inject` is `False`
- **THEN** the controller SHALL call `PolishEngine.polish()` and inject the polished result

#### Scenario: Polish failure fallback

- **WHEN** `PolishEngine.polish()` raises an exception
- **THEN** the controller SHALL log the error and inject the original ASR text without raising an error state

---
### Requirement: Polish Preview Dialog Integration

When `config.llm.preview_before_inject` is `True`, `CoreController` SHALL display `PolishPreviewDialog` showing both the original and polished text. The controller SHALL inject whichever version the user selects. If the user dismisses the dialog without selecting, the controller SHALL inject the original text.

#### Scenario: User selects polished text

- **WHEN** `preview_before_inject` is `True` and the user selects the polished version in the dialog
- **THEN** the controller SHALL inject the polished text

#### Scenario: User selects original text

- **WHEN** `preview_before_inject` is `True` and the user selects the original version in the dialog
- **THEN** the controller SHALL inject the original text

#### Scenario: User dismisses dialog

- **WHEN** `preview_before_inject` is `True` and the user closes the dialog without selecting
- **THEN** the controller SHALL inject the original text

---
### Requirement: PolishEngine Dependency Injection into CoreController

`CoreController.__init__()` SHALL accept an optional `polish_engine` parameter of type `PolishEngine`. When `polish_engine` is `None` or not provided, LLM polishing SHALL be treated as disabled regardless of `config.llm.enabled`.

#### Scenario: No polish engine provided

- **WHEN** `CoreController` is constructed without a `polish_engine` argument
- **THEN** the controller SHALL inject original ASR text directly without attempting to polish
