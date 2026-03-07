## MODIFIED Requirements

### Requirement: Model Card Display

Each model card SHALL be a `QFrame` displaying the model name on the first line (bold, 13px) and a description subtitle on the second line (gray, 11px). The description subtitle SHALL be extracted from the manifest `description` field by splitting on the full-width left parenthesis character `（`: the text before the parenthesis becomes the model name, and the text inside the parentheses (with surrounding `（` and `）` removed) becomes the subtitle. If the description does not contain `（`, the entire description SHALL be used as the model name and the subtitle SHALL be hidden. The card SHALL also display the human-readable file size (e.g., "650 MB", "1.7 GB"). If the model is the hardware-recommended model (as determined by `HardwareDetector`), the card SHALL display a "Recommended" badge next to the model name.

#### Scenario: Card shows model information with two-line layout

- **WHEN** a model card is rendered for a manifest entry whose description contains `（`
- **THEN** the card SHALL display the text before `（` as the model name in bold on the first line
- **THEN** the card SHALL display the text inside the parentheses as a gray subtitle on the second line
- **THEN** the card SHALL display the file size in human-readable format below the subtitle

#### Scenario: Card shows model without parenthetical description

- **WHEN** a model card is rendered for a manifest entry whose description does not contain `（`
- **THEN** the card SHALL display the entire description as the model name in bold on the first line
- **THEN** the subtitle line SHALL be hidden

#### Scenario: Recommended badge displayed

- **WHEN** a model card corresponds to the hardware-recommended model
- **THEN** the card SHALL display a visually distinct "Recommended" badge

#### Scenario: Non-recommended model

- **WHEN** a model card does not correspond to the hardware-recommended model
- **THEN** the card SHALL NOT display a "Recommended" badge

### Requirement: Model Management Settings Page

The settings panel SHALL provide a Model Management page (`SettingsModelsPage`) that displays all models from the manifest in a card-based scrollable list. The page SHALL include a `QTabBar` with two tabs: one for ASR models and one for LLM models. Switching tabs SHALL repopulate the card list with models of the selected category. The `QScrollArea` containing the card list SHALL have horizontal scrollbar disabled (`ScrollBarAlwaysOff`).

#### Scenario: Open model management page

- **WHEN** the user navigates to the Model Management page
- **THEN** the page SHALL display a tab bar with ASR and LLM tabs, defaulting to the ASR tab
- **THEN** the card list SHALL show all ASR models from the manifest
- **THEN** no horizontal scrollbar SHALL be visible

#### Scenario: Switch to LLM tab

- **WHEN** the user clicks the LLM tab
- **THEN** the card list SHALL be repopulated with all LLM models from the manifest

### Requirement: Model Card Download State

Each model card SHALL display one of three mutually exclusive states based on the model's download status. The action area on the right side of the card SHALL have a fixed width of 90px. All action buttons and the progress bar SHALL have a fixed width of 80px.

1. **Not downloaded**: A "Download" button (80px wide) SHALL be visible.
2. **Downloading**: A progress bar (80px wide), percentage label, and "Cancel" button (80px wide) SHALL be visible.
3. **Downloaded**: A green checkmark icon and a "Delete" button (80px wide) SHALL be visible.

State transitions SHALL use `setVisible()` to switch between the three state containers.

#### Scenario: Model not yet downloaded

- **WHEN** a model card is rendered for a model that is not downloaded
- **THEN** the card SHALL display a "Download" button and hide the progress and downloaded indicators

#### Scenario: Model download in progress

- **WHEN** a model download is in progress
- **THEN** the card SHALL display a progress bar with percentage and a "Cancel" button, and hide the download button and downloaded indicator

#### Scenario: Model already downloaded

- **WHEN** a model card is rendered for a model that is already downloaded
- **THEN** the card SHALL display a green checkmark and a "Delete" button, and hide the download button and progress indicator
