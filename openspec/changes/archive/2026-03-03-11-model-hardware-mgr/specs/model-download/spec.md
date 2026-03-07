## ADDED Requirements

### Requirement: Model Download with Progress

The system SHALL download ASR models from HuggingFace with real-time progress reporting (bytes downloaded, total size, percentage, and estimated time remaining).

#### Scenario: Download with Progress Callback

- **WHEN** a model download is started with a progress callback
- **THEN** the callback SHALL be invoked periodically with download progress information

### Requirement: Download Integrity Verification

The system SHALL verify downloaded model files using SHA-256 checksums after download completes. If verification fails, the downloaded file SHALL be deleted and the download SHALL be retried.

#### Scenario: Checksum Matches

- **WHEN** a model download completes and the SHA-256 matches the expected hash
- **THEN** the model SHALL be marked as available for use

#### Scenario: Checksum Mismatch

- **WHEN** a model download completes but the SHA-256 does not match
- **THEN** the downloaded file SHALL be deleted and an error SHALL be reported

### Requirement: Fallback Download URLs

The system SHALL support fallback download URLs for each model. If the primary URL fails, the system SHALL automatically attempt the next fallback URL.

#### Scenario: Primary URL Fails

- **WHEN** the primary HuggingFace URL returns an error
- **THEN** the system SHALL automatically attempt to download from the fallback URL

### Requirement: Disk Space Validation

The system SHALL check available disk space before starting a download. If space is insufficient, the download SHALL NOT start and an error SHALL be reported.

#### Scenario: Insufficient Disk Space

- **WHEN** the required model size exceeds available disk space
- **THEN** the system SHALL report an error including the required and available space

### Requirement: Model Manifest

The system SHALL maintain a model manifest (`models/manifest.json`) describing available models with their IDs, file sizes, download URLs, fallback URLs, and SHA-256 checksums.

#### Scenario: Read Manifest

- **WHEN** the model manager initializes
- **THEN** it SHALL load the manifest and determine which models are available for download
