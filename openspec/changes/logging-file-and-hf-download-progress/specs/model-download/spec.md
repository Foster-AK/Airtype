## MODIFIED Requirements

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
