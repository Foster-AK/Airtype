## ADDED Requirements

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

### Requirement: Token value not logged

The system SHALL NOT log the token value in any log level. The system SHALL log only whether a token was found (e.g., "HF token attached") at DEBUG level.

#### Scenario: Token presence logged at debug level

- **WHEN** a HuggingFace token is found and attached to a download request
- **THEN** the system SHALL log a debug message indicating a token was attached without revealing the token value
