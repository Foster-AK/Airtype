# Model Download Spec

## Requirement: Model Download with Progress

The system SHALL download ASR models from HuggingFace with real-time progress reporting (bytes downloaded, total size, percentage, and estimated time remaining).

### Scenario: Download with Progress Callback

- **WHEN** a model download is started with a progress callback
- **THEN** the callback SHALL be invoked periodically with download progress information

## Requirement: Download Integrity Verification

The system SHALL verify downloaded model files using SHA-256 checksums after download completes. If verification fails, the downloaded file SHALL be deleted and the download SHALL be retried.

### Scenario: Checksum Matches

- **WHEN** a model download completes and the SHA-256 matches the expected hash
- **THEN** the model SHALL be marked as available for use

### Scenario: Checksum Mismatch

- **WHEN** a model download completes but the SHA-256 does not match
- **THEN** the downloaded file SHALL be deleted and an error SHALL be reported

## Requirement: Fallback Download URLs

The system SHALL support fallback download URLs for each model. If the primary URL fails, the system SHALL automatically attempt the next fallback URL.

### Scenario: Primary URL Fails

- **WHEN** the primary HuggingFace URL returns an error
- **THEN** the system SHALL automatically attempt to download from the fallback URL

## Requirement: Disk Space Validation

The system SHALL check available disk space before starting a download. If space is insufficient, the download SHALL NOT start and an error SHALL be reported.

### Scenario: Insufficient Disk Space

- **WHEN** the required model size exceeds available disk space
- **THEN** the system SHALL report an error including the required and available space

## Requirement: Model Manifest

The system SHALL maintain a model manifest (`models/manifest.json`) describing available models with their IDs, file sizes, download URLs, fallback URLs, and SHA-256 checksums.

### Scenario: Read Manifest

- **WHEN** the model manager initializes
- **THEN** it SHALL load the manifest and determine which models are available for download

## Requirements

### Requirement: Model Download with Progress

The system SHALL download ASR models from HuggingFace with real-time progress reporting (bytes downloaded, total size, percentage, and estimated time remaining). For HuggingFace repository downloads (multi-file models via `snapshot_download`), the system SHALL aggregate progress across all files and report intermediate progress through the progress callback, not only at 0% and 100%.

#### Scenario: Download with Progress Callback

- **WHEN** a model download is started with a progress callback
- **THEN** the callback SHALL be invoked periodically with download progress information

#### Scenario: HuggingFace repo download reports intermediate progress

- **WHEN** a multi-file model is downloaded via `snapshot_download` with a progress callback
- **THEN** the callback SHALL be invoked with aggregated intermediate progress (bytes downloaded across all files, total bytes, percentage, and ETA) as each chunk is received

#### Scenario: HuggingFace repo download without callback

- **WHEN** a multi-file model is downloaded via `snapshot_download` without a progress callback
- **THEN** the download SHALL complete normally without injecting any progress tracking


<!-- @trace
source: logging-file-and-hf-download-progress
updated: 2026-03-07
code:
  - resources/icons/airtype1024.icns
  - resources/icons/airtype_icon_486.ico
  - airtype/utils/hardware_detect.py
  - airtype/core/asr_qwen_vulkan.py
  - airtype/__main__.py
  - installer/windows/airtype.nsi
  - airtype/logging_setup.py
  - airtype/utils/model_manager.py
tests:
  - tests/test_logging_setup.py
  - tests/test_model_manager_hf_progress.py
-->

---
### Requirement: Download Integrity Verification

The system SHALL verify downloaded model files using SHA-256 checksums after download completes. If verification fails, the downloaded file SHALL be deleted and the download SHALL be retried.

#### Scenario: Checksum Matches

- **WHEN** a model download completes and the SHA-256 matches the expected hash
- **THEN** the model SHALL be marked as available for use

#### Scenario: Checksum Mismatch

- **WHEN** a model download completes but the SHA-256 does not match
- **THEN** the downloaded file SHALL be deleted and an error SHALL be reported

---
### Requirement: Fallback Download URLs

The system SHALL support fallback download URLs for each model. If the primary URL fails, the system SHALL automatically attempt the next fallback URL.

#### Scenario: Primary URL Fails

- **WHEN** the primary HuggingFace URL returns an error
- **THEN** the system SHALL automatically attempt to download from the fallback URL

---
### Requirement: Disk Space Validation

The system SHALL check available disk space before starting a download. If space is insufficient, the download SHALL NOT start and an error SHALL be reported.

#### Scenario: Insufficient Disk Space

- **WHEN** the required model size exceeds available disk space
- **THEN** the system SHALL report an error including the required and available space

---
### Requirement: Model Manifest

The system SHALL maintain a model manifest (`models/manifest.json`) describing available models with their IDs, file sizes, download URLs, fallback URLs, and SHA-256 checksums.

#### Scenario: Read Manifest

- **WHEN** the model manager initializes
- **THEN** it SHALL load the manifest and determine which models are available for download

---
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

---
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

---
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

---
### Requirement: HuggingFace Token Authentication

The system SHALL automatically detect and attach a HuggingFace authentication token when downloading from `huggingface.co` URLs. The token SHALL be resolved from the following sources in priority order:

1. System keyring (`provider="huggingface"`)
2. Environment variable `HF_TOKEN`
3. Local cache file at `~/.cache/huggingface/token`

If no token is found from any source, the download SHALL proceed without authentication.

#### Scenario: Download with keyring token

- **WHEN** a HuggingFace URL download is initiated and a token exists in the system keyring for provider `"huggingface"`
- **THEN** the system SHALL include an `Authorization: Bearer <token>` header in the HTTP request

#### Scenario: Download with environment variable token

- **WHEN** a HuggingFace URL download is initiated and no keyring token exists but the `HF_TOKEN` environment variable is set
- **THEN** the system SHALL use the environment variable value as the Bearer token

#### Scenario: Download with cached token file

- **WHEN** a HuggingFace URL download is initiated and no keyring or environment token exists but `~/.cache/huggingface/token` contains a non-empty value
- **THEN** the system SHALL use the cached file content as the Bearer token

#### Scenario: Download without token — use fallback URL

- **WHEN** a HuggingFace URL download is initiated and no token is available from any source and `fallback_urls` are defined in the manifest
- **THEN** the system SHALL use a fallback URL instead of the primary HuggingFace URL, without an Authorization header

#### Scenario: Download without token and no fallback URL

- **WHEN** a HuggingFace URL download is initiated and no token is available from any source and no `fallback_urls` are defined
- **THEN** the system SHALL proceed with the primary URL without an Authorization header

#### Scenario: Non-HuggingFace URL unaffected

- **WHEN** a download is initiated for a URL that does not contain `huggingface.co`
- **THEN** the system SHALL NOT attach any Authorization header regardless of token availability

---
### Requirement: Token value not logged

The system SHALL NOT log the token value in any log level. The system SHALL log only whether a token was found (e.g., "HF token attached") at DEBUG level.

#### Scenario: Token presence logged at debug level

- **WHEN** a HuggingFace token is found and attached to a download request
- **THEN** the system SHALL log a debug message indicating a token was attached without revealing the token value