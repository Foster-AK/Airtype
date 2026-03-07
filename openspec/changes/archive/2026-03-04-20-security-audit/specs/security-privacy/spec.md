## ADDED Requirements

### Requirement: Audio Data Non-Persistence

The system SHALL NOT write audio data to any persistent storage (disk, database). Audio SHALL exist only in memory during processing and SHALL be released immediately after recognition is complete.

#### Scenario: Verify No Audio Files

- **WHEN** a complete recognition cycle ends
- **THEN** the application data directory SHALL NOT contain any audio files

### Requirement: API Key Encryption via System keyring

API keys SHALL be stored using the Python `keyring` package, backed by the system keyring (Windows: Credential Manager, macOS: Keychain, Linux: Secret Service). Keys SHALL NOT be stored in plaintext within configuration files.

#### Scenario: Store API Key

- **WHEN** the user enters an API key in settings
- **THEN** the key SHALL be stored in the system keyring rather than in config.json

### Requirement: Configuration Directory Permissions

The `~/.airtype/` directory SHALL have `0o700` permissions (user-access only) on Unix systems. The system SHALL verify permissions at startup.

#### Scenario: Verify Permissions at Startup

- **WHEN** the application starts
- **THEN** it SHALL check whether `~/.airtype/` has restricted permissions and SHALL emit a warning if the check fails

### Requirement: Log Sanitization via Custom Formatter

Application logs SHALL NOT contain user-recognized text, audio content, or API keys. A log sanitization filter SHALL redact any sensitive content.

#### Scenario: Logs Do Not Contain Recognized Text

- **WHEN** the text "my password is 12345" is recognized
- **THEN** the application log SHALL NOT contain that text

### Requirement: Automated Test Suite for Security Audit

Security validation SHALL be implemented as an automated test suite (pytest) that can be executed as part of CI.

#### Scenario: Run Security Tests

- **WHEN** `pytest tests/test_security.py` is executed
- **THEN** all security audit tests SHALL pass
