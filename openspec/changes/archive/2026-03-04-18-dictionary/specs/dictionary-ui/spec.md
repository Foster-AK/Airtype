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
