## ADDED Requirements

### Requirement: Dictionary Settings Page

The settings panel SHALL provide a dictionary page containing editable table components for hot words (term, weight, and enabled toggle) and replacement rules (source, target, regex toggle, and enabled toggle).

#### Scenario: Adding a hot word

- **WHEN** the user clicks "Add" and enters "PostgreSQL" with a weight of 9
- **THEN** the hot word SHALL be added to the current dictionary and saved

### Requirement: Dictionary Import and Export

The dictionary page SHALL support importing from .txt, .csv, and .json files, and exporting to the same formats. Dictionary sets SHALL be exportable as `.airtype-dict` files for sharing.

#### Scenario: Importing CSV hot words

- **WHEN** the user imports a CSV file containing "word" and "weight" columns
- **THEN** all entries SHALL be added to the current hot word list

#### Scenario: Exporting a dictionary set

- **WHEN** the user exports a dictionary set
- **THEN** a `.airtype-dict` JSON file containing the hot words and replacement rules SHALL be created

### Requirement: Dictionary Files Stored as JSON

Each dictionary set SHALL be stored as a JSON file with the structure: `{"hot_words": [{"word", "weight", "enabled"}], "replace_rules": [{"from", "to", "regex", "enabled"}]}`.

#### Scenario: Loading dictionary files

- **WHEN** the application starts
- **THEN** all dictionary sets located under `~/.airtype/dictionaries/` SHALL be loaded

## Requirements

### Requirement: Dictionary Settings Page

The settings panel SHALL provide a dictionary page containing editable table components for hot words (term, weight, and enabled toggle) and replacement rules (source, target, regex toggle, and enabled toggle).

#### Scenario: Adding a hot word

- **WHEN** the user clicks "Add" and enters "PostgreSQL" with a weight of 9
- **THEN** the hot word SHALL be added to the current dictionary and saved

---
### Requirement: Dictionary Import and Export

The dictionary page SHALL support importing from .txt, .csv, and .json files, and exporting to the same formats. Dictionary sets SHALL be exportable as `.airtype-dict` files for sharing.

#### Scenario: Importing CSV hot words

- **WHEN** the user imports a CSV file containing "word" and "weight" columns
- **THEN** all entries SHALL be added to the current hot word list

#### Scenario: Exporting a dictionary set

- **WHEN** the user exports a dictionary set
- **THEN** a `.airtype-dict` JSON file containing the hot words and replacement rules SHALL be created

---
### Requirement: Dictionary Files Stored as JSON

Each dictionary set SHALL be stored as a JSON file with the structure: `{"hot_words": [{"word", "weight", "enabled"}], "replace_rules": [{"from", "to", "regex", "enabled"}]}`.

#### Scenario: Loading dictionary files

- **WHEN** the application starts
- **THEN** all dictionary sets located under `~/.airtype/dictionaries/` SHALL be loaded

---
### Requirement: Dictionary Page Layout Uses QHBoxLayout

The dictionary settings page SHALL use a `QHBoxLayout` to arrange the dictionary set panel (left) and the hot words / replace rules panel (right). The page SHALL NOT use a resizable splitter (`QSplitter`) for this layout. The two panels SHALL be displayed adjacent to each other with no empty space between them upon first display.

#### Scenario: First display with no prior user interaction

- **WHEN** the user opens the settings panel and navigates to the dictionary page
- **THEN** the dictionary set panel (left) and hot words panel (right) SHALL be visually adjacent with no gap between them

---
### Requirement: Dictionary Set Panel Uses QGroupBox

The dictionary set panel SHALL be presented as a `QGroupBox` with a title, consistent with the hot words and replace rules panels on the right side. The panel SHALL have a fixed width of 160px.

#### Scenario: Visual consistency with other panels

- **WHEN** the dictionary page is displayed
- **THEN** all three panels (dictionary sets, hot words, replace rules) SHALL be rendered as `QGroupBox` elements with titles

---
### Requirement: Dictionary Set Creation Updates UI Immediately

After a new dictionary set is successfully created, the dictionary sets list SHALL be refreshed and the newly created set SHALL be automatically selected and displayed in the editing panels.

#### Scenario: Adding a new dictionary set with engine available

- **WHEN** the user clicks the "+" button, enters a valid set name, and confirms
- **THEN** the new dictionary set SHALL appear in the sets list and SHALL be automatically selected as the current set

#### Scenario: Adding a new dictionary set when engine is unavailable

- **WHEN** the dictionary engine has not been initialized and the user attempts to add a set
- **THEN** the UI SHALL display a warning message and SHALL NOT attempt to create a set

---
### Requirement: Checkbox Items Render Correctly on All Platforms

The enabled toggle and regex toggle columns in the hot words and replacement rules tables SHALL render as standard checkbox controls (empty square when unchecked, square with checkmark when checked) on all supported platforms including Windows, under both light and dark themes.

The implementation SHALL use `QCheckBox` widgets via `setCellWidget()` rather than `QTableWidgetItem` checkstate, to ensure OS-native rendering that is independent of the `QAbstractItemView` palette.

#### Scenario: Enabled checkbox in Checked state

- **WHEN** a hot word or replacement rule has `enabled: true`
- **THEN** the checkbox in the enabled column SHALL display a visible checkmark indicator in both light and dark themes

#### Scenario: Enabled checkbox in Unchecked state

- **WHEN** a hot word or replacement rule has `enabled: false`
- **THEN** the checkbox in the enabled column SHALL display an empty box without a filled black square in both light and dark themes

#### Scenario: Regex checkbox in Checked state

- **WHEN** a replacement rule has `regex: true`
- **THEN** the checkbox in the regex column SHALL display a visible checkmark indicator in both light and dark themes

#### Scenario: Checkbox state is readable after user interaction

- **WHEN** the user toggles a checkbox widget in the enabled or regex column
- **THEN** the updated state SHALL be reflected in the engine flush and persisted to storage
