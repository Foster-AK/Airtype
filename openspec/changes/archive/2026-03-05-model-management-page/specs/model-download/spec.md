## ADDED Requirements

### Requirement: Delete Downloaded Model

The `ModelManager` SHALL provide a `delete_model(model_id: str) -> bool` method that deletes the downloaded model file from the local model directory. The method SHALL return `True` if the file was successfully deleted, and `False` if the file did not exist. The method SHALL raise `KeyError` if the `model_id` is not present in the manifest.

#### Scenario: Delete existing model file

- **WHEN** `delete_model("qwen3-asr-0.6b-openvino")` is called and the model file exists
- **THEN** the file SHALL be deleted from the download directory and the method SHALL return `True`

#### Scenario: Delete non-existent model file

- **WHEN** `delete_model("qwen3-asr-0.6b-openvino")` is called and the model file does not exist
- **THEN** the method SHALL return `False` without raising an error

#### Scenario: Delete unknown model ID

- **WHEN** `delete_model("nonexistent-model")` is called with an ID not in the manifest
- **THEN** the method SHALL raise a `KeyError`

### Requirement: Get Model File Path

The `ModelManager` SHALL provide a `get_model_path(model_id: str) -> Optional[str]` method that returns the absolute file path of a downloaded model. If the model is not downloaded, the method SHALL return `None`. If the `model_id` is not in the manifest, the method SHALL return `None`.

#### Scenario: Get path of downloaded model

- **WHEN** `get_model_path("qwen3-asr-0.6b-openvino")` is called and the model file exists
- **THEN** the method SHALL return the absolute file path as a string

#### Scenario: Get path of non-downloaded model

- **WHEN** `get_model_path("qwen3-asr-0.6b-openvino")` is called and the model file does not exist
- **THEN** the method SHALL return `None`

#### Scenario: Get path of unknown model ID

- **WHEN** `get_model_path("nonexistent-model")` is called
- **THEN** the method SHALL return `None`
