## MODIFIED Requirements

### Requirement: Delete Downloaded Model

The `ModelManager` SHALL provide a `delete_model(model_id: str) -> bool` method that deletes the downloaded model file or directory from the local model directory. For models whose `filename` ends with `.zip`, the method SHALL also attempt to delete the extracted directory (filename without the `.zip` extension) using recursive removal. The method SHALL return `True` if any file or directory was successfully deleted, and `False` if neither the file nor the directory existed. The method SHALL raise `KeyError` if the `model_id` is not present in the manifest.

#### Scenario: Delete existing model file

- **WHEN** `delete_model("qwen2.5-1.5b")` is called and the model file exists as a single file
- **THEN** the file SHALL be deleted from the download directory and the method SHALL return `True`

#### Scenario: Delete existing model directory

- **WHEN** `delete_model("qwen3-asr-0.6b-openvino")` is called and the model exists as an extracted directory (filename without `.zip` extension)
- **THEN** the directory SHALL be recursively deleted from the download directory and the method SHALL return `True`

#### Scenario: Delete model with both zip file and extracted directory

- **WHEN** `delete_model("qwen3-asr-0.6b-openvino")` is called and both the `.zip` file and the extracted directory exist
- **THEN** both the `.zip` file and the directory SHALL be deleted and the method SHALL return `True`

#### Scenario: Delete non-existent model file

- **WHEN** `delete_model("qwen3-asr-0.6b-openvino")` is called and neither the model file nor directory exists
- **THEN** the method SHALL return `False` without raising an error

#### Scenario: Delete unknown model ID

- **WHEN** `delete_model("nonexistent-model")` is called with an ID not in the manifest
- **THEN** the method SHALL raise a `KeyError`
