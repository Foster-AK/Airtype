## ADDED Requirements

### Requirement: OpenAI-Compatible API Integration

The system SHALL support text polishing via OpenAI-compatible API endpoints. Supported providers SHALL include Anthropic Claude, OpenAI, Ollama (local), and custom endpoints.

#### Scenario: API polishing

- **WHEN** the user has configured an OpenAI API key and endpoint
- **THEN** the system SHALL send the text to the API and return the polished result

#### Scenario: API error fallback

- **WHEN** an API call fails due to a network error or authentication error
- **THEN** the system SHALL return the original unpolished text and log the error

### Requirement: OpenAI-Compatible API Calls via httpx

All API providers SHALL use the OpenAI chat completions format via `httpx.AsyncClient`, with configurable `base_url` and API key.

#### Scenario: Custom endpoint

- **WHEN** a custom OpenAI-compatible endpoint is configured
- **THEN** the system SHALL use that endpoint for all API calls

### Requirement: Polish Preview UI

The system SHALL provide a preview dialog that displays the original text and the polished text side by side. The user SHALL choose which version to inject.

#### Scenario: Showing the preview

- **WHEN** `llm.preview_before_inject` is enabled
- **THEN** the preview dialog SHALL display both versions and wait for the user's selection
