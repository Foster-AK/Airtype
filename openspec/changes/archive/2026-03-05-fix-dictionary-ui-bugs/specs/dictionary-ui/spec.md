## ADDED Requirements

### Requirement: Dictionary Set Creation Updates UI Immediately

After a new dictionary set is successfully created, the dictionary sets list SHALL be refreshed and the newly created set SHALL be automatically selected and displayed in the editing panels.

#### Scenario: Adding a new dictionary set with engine available

- **WHEN** the user clicks the "+" button, enters a valid set name, and confirms
- **THEN** the new dictionary set SHALL appear in the sets list and SHALL be automatically selected as the current set

#### Scenario: Adding a new dictionary set when engine is unavailable

- **WHEN** the dictionary engine has not been initialized and the user attempts to add a set
- **THEN** the UI SHALL display a warning message and SHALL NOT attempt to create a set

### Requirement: Checkbox Items Render Correctly on All Platforms

The enabled toggle and regex toggle columns in the hot words and replacement rules tables SHALL render as standard checkbox controls (empty square when unchecked, square with checkmark when checked) on all supported platforms including Windows.

#### Scenario: Enabled checkbox in Checked state

- **WHEN** a hot word or replacement rule has `enabled: true`
- **THEN** the checkbox in the enabled column SHALL display a visible checkmark indicator

#### Scenario: Enabled checkbox in Unchecked state

- **WHEN** a hot word or replacement rule has `enabled: false`
- **THEN** the checkbox in the enabled column SHALL display an empty box without a filled black square

#### Scenario: Regex checkbox in Checked state

- **WHEN** a replacement rule has `regex: true`
- **THEN** the checkbox in the regex column SHALL display a visible checkmark indicator
