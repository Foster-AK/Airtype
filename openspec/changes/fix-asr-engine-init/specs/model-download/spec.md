## ADDED Requirements

### Requirement: Model File Integrity Validation

The system SHALL provide a `validate_model_files()` method on `ModelManager` that verifies the presence of required files within a downloaded model directory. The method SHALL accept a `model_id` and an optional list of `required_files`. Each entry in `required_files` SHALL support `"A OR B"` syntax, meaning at least one of the alternatives MUST exist for validation to pass. The method SHALL also detect `.tmp` temporary files that indicate incomplete downloads. The method SHALL return a tuple of `(is_valid, missing_files, tmp_files)`.

#### Scenario: All Required Files Present

- **WHEN** `validate_model_files()` is called with a model ID whose directory contains all required files and no `.tmp` files
- **THEN** the method SHALL return `(True, [], [])`

#### Scenario: Missing Required File

- **WHEN** `validate_model_files()` is called and `encoder.onnx` is missing from the model directory
- **THEN** `is_valid` SHALL be `False`
- **THEN** `missing_files` SHALL contain the missing file name

#### Scenario: OR Syntax Satisfied

- **WHEN** `required_files` contains `"encoder.onnx OR encoder.int8.onnx"` and `encoder.int8.onnx` exists but `encoder.onnx` does not
- **THEN** the requirement SHALL pass validation (not listed as missing)

#### Scenario: OR Syntax Not Satisfied

- **WHEN** `required_files` contains `"encoder.onnx OR encoder.int8.onnx"` and neither file exists
- **THEN** `missing_files` SHALL contain `"encoder.onnx OR encoder.int8.onnx"`

#### Scenario: Temporary Files Detected

- **WHEN** the model directory contains files ending in `.tmp`
- **THEN** `tmp_files` SHALL contain the names of those temporary files
- **THEN** `is_valid` SHALL be `False`

#### Scenario: No Required Files Specified

- **WHEN** `validate_model_files()` is called with `required_files=None`
- **THEN** only `.tmp` file detection SHALL be performed
- **THEN** if no `.tmp` files exist, the method SHALL return `(True, [], [])`

### Requirement: ASR Engine Required Files Declaration

Each ASR engine class SHALL declare a `REQUIRED_FILES` class attribute listing the files necessary for the engine to function. The `QwenOnnxEngine` SHALL declare required files including encoder, decoder init, decoder step, embed tokens, and config files using `"A OR B"` syntax for variant support.

#### Scenario: QwenOnnxEngine Declares Required Files

- **WHEN** `QwenOnnxEngine.REQUIRED_FILES` is accessed
- **THEN** it SHALL contain entries for `encoder.onnx OR encoder.int8.onnx`, `decoder_init.onnx OR decoder_init.int8.onnx`, `decoder_step.onnx OR decoder_step.int8.onnx`, `embed_tokens.bin`, and `config.json`
