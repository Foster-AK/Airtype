## ADDED Requirements

### Requirement: Hot Words Engine Support Warning

The dictionary settings page SHALL display a warning label in the hot words section when the currently active ASR engine does not support hot word boosting. The warning SHALL inform the user that hot words are ineffective with the current engine and suggest using replacement rules as an alternative. The hot word editing controls SHALL remain enabled regardless of engine support.

#### Scenario: Warning shown for unsupported engine

- **WHEN** the dictionary settings page is displayed and the active ASR engine has `supports_hot_words == False`
- **THEN** a warning label SHALL be visible in the hot words section

#### Scenario: Warning hidden for supported engine

- **WHEN** the dictionary settings page is displayed and the active ASR engine has `supports_hot_words == True`
- **THEN** the warning label SHALL be hidden

#### Scenario: Warning updates on engine switch

- **WHEN** the user switches from a supported engine to an unsupported engine while the dictionary page is open
- **THEN** the warning label SHALL become visible without requiring the user to close and reopen the page

#### Scenario: Hot word editing remains enabled

- **WHEN** the active engine does not support hot words
- **THEN** the hot word table and add/delete buttons SHALL remain interactive
