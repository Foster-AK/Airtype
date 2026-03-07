## ADDED Requirements

### Requirement: HuggingFace Token Input

The model management settings page SHALL provide a token input field that allows users to enter a HuggingFace Access Token for downloading gated models.

#### Scenario: User enters HuggingFace token

- **WHEN** the user enters a non-empty value in the HuggingFace token input field and confirms
- **THEN** the system SHALL store the token in the system keyring via `config.set_api_key("huggingface", token)`

#### Scenario: User clears HuggingFace token

- **WHEN** the user clears or explicitly removes the HuggingFace token via the clear button
- **THEN** the system SHALL remove the token from the system keyring via `config.set_api_key("huggingface", "")`

#### Scenario: Token field displayed with password masking

- **WHEN** the token input field is displayed
- **THEN** the field SHALL mask the input value (echoMode=Password) and display a label explaining the field is optional and that downloads will use a public mirror if no token is provided

#### Scenario: Token field initialized with existing keyring value

- **WHEN** the model management page is loaded and a token exists in the system keyring for provider `"huggingface"`
- **THEN** the token input field SHALL display a placeholder mask (e.g., `hf_****`) to indicate a token is stored, without revealing the actual value

#### Scenario: Token field initialized without existing keyring value

- **WHEN** the model management page is loaded and no token exists in the system keyring for provider `"huggingface"`
- **THEN** the token input field SHALL be empty with a placeholder text prompting the user to enter a token

### Requirement: HuggingFace 401 Error Guidance

The settings model page SHALL display a guidance message when a model download fails with an HTTP 401 Unauthorized error. The message SHALL inform the user how to provide a HuggingFace token via one of the supported methods (environment variable `HF_TOKEN` or `huggingface-cli login`).

#### Scenario: Download fails with 401

- **WHEN** a model download fails and the error message contains "401"
- **THEN** the model card SHALL display a guidance message instructing the user to set a HuggingFace token

#### Scenario: Download fails with non-401 error

- **WHEN** a model download fails with an error that does not contain "401"
- **THEN** the model card SHALL display the standard error message without HuggingFace token guidance
