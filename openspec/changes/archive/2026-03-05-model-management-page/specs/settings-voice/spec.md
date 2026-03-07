## MODIFIED Requirements

### Requirement: Manifest-Driven ASR Model List

The ASR model dropdown SHALL be populated by calling `ModelManager.list_models_by_category("asr")` at settings page initialization. The dropdown SHALL display only models that are already downloaded locally (`ModelManager.is_downloaded()` returns `True`). Each entry SHALL display the model's `description` field as the label and use its `id` field as the value. If no models are downloaded, the dropdown SHALL display a placeholder text "(No downloaded models)" and SHALL be disabled. A hint label below the dropdown SHALL display a message directing the user to the Model Management page to download ASR models.

#### Scenario: Models Loaded from Manifest

- **WHEN** the Voice settings page is opened and downloaded ASR models exist
- **THEN** the ASR model dropdown SHALL contain only the downloaded entries returned by `list_models_by_category("asr")` with their description as the display label

#### Scenario: No Downloaded Models

- **WHEN** the Voice settings page is opened and no ASR models are downloaded
- **THEN** the dropdown SHALL display "(No downloaded models)" as a placeholder
- **THEN** the dropdown SHALL be disabled
- **THEN** a hint label SHALL be visible directing the user to the Model Management page

#### Scenario: Undownloaded Model Excluded

- **WHEN** a manifest ASR model is not present in the local model directory
- **THEN** the dropdown SHALL NOT include that model in the list
