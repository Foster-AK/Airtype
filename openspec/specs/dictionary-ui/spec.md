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

---
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

<!-- @trace
source: hot-words-engine-sync
updated: 2026-03-07
code:
  - airtype/core/asr_qwen_pytorch.py
  - locales/zh_CN.json
  - airtype/core/asr_qwen_openvino.py
  - airtype/ui/settings_window.py
  - locales/zh_TW.json
  - airtype/core/asr_qwen_vulkan.py
  - airtype/core/asr_sherpa.py
  - airtype/core/asr_breeze.py
  - airtype/core/asr_engine.py
  - airtype/__main__.py
  - airtype/ui/settings_dictionary.py
  - locales/en.json
  - locales/ja.json
tests:
  - tests/test_asr_engine.py
  - tests/test_asr_sherpa.py
-->