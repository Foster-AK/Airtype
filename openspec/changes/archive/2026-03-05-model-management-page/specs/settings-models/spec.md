## ADDED Requirements

### Requirement: Model Management Settings Page

The settings panel SHALL provide a Model Management page (`SettingsModelsPage`) that displays all models from the manifest in a card-based scrollable list. The page SHALL include a `QTabBar` with two tabs: one for ASR models and one for LLM models. Switching tabs SHALL repopulate the card list with models of the selected category.

#### Scenario: Open model management page

- **WHEN** the user navigates to the Model Management page
- **THEN** the page SHALL display a tab bar with ASR and LLM tabs, defaulting to the ASR tab
- **THEN** the card list SHALL show all ASR models from the manifest

#### Scenario: Switch to LLM tab

- **WHEN** the user clicks the LLM tab
- **THEN** the card list SHALL be repopulated with all LLM models from the manifest

### Requirement: Model Card Display

Each model card SHALL be a `QFrame` displaying the model name, description text, and human-readable file size (e.g., "650 MB", "1.7 GB"). If the model is the hardware-recommended model (as determined by `HardwareDetector`), the card SHALL display a "Recommended" badge next to the model name.

#### Scenario: Card shows model information

- **WHEN** a model card is rendered for a manifest entry
- **THEN** the card SHALL display the model's description as the title, a brief text description, and the file size in human-readable format

#### Scenario: Recommended badge displayed

- **WHEN** a model card corresponds to the hardware-recommended model
- **THEN** the card SHALL display a visually distinct "Recommended" badge

#### Scenario: Non-recommended model

- **WHEN** a model card does not correspond to the hardware-recommended model
- **THEN** the card SHALL NOT display a "Recommended" badge

### Requirement: Model Card Download State

Each model card SHALL display one of three mutually exclusive states based on the model's download status:

1. **Not downloaded**: A "Download" button SHALL be visible.
2. **Downloading**: A progress bar, percentage label, and "Cancel" button SHALL be visible.
3. **Downloaded**: A green checkmark icon and a "Delete" button SHALL be visible.

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

### Requirement: Background Model Download

Model downloads SHALL execute in a background `QThread` (`DownloadWorker`) to avoid blocking the UI. The worker SHALL emit progress signals that update the card's progress bar in real time. At most one download SHALL be active at any time; while a download is in progress, all other cards' download buttons SHALL be disabled.

#### Scenario: Start download

- **WHEN** the user clicks the "Download" button on a model card
- **THEN** a `DownloadWorker` SHALL be started in a background thread
- **THEN** the card SHALL transition to the "downloading" state
- **THEN** all other cards' download buttons SHALL be disabled

#### Scenario: Download progress update

- **WHEN** the `DownloadWorker` emits a progress signal
- **THEN** the card's progress bar and percentage label SHALL be updated

#### Scenario: Download completes successfully

- **WHEN** the `DownloadWorker` emits a finished signal
- **THEN** the card SHALL transition to the "downloaded" state
- **THEN** all other cards' download buttons SHALL be re-enabled
- **THEN** a `model_downloaded` signal SHALL be emitted to notify dependent pages

#### Scenario: Download fails

- **WHEN** the `DownloadWorker` emits an error signal
- **THEN** the card SHALL transition back to the "not downloaded" state
- **THEN** an error message SHALL be displayed to the user

### Requirement: Cancel Download

The user SHALL be able to cancel an in-progress download by clicking the "Cancel" button. Cancellation SHALL set a flag that causes the download worker's progress callback to raise an exception, interrupting the download loop.

#### Scenario: Cancel active download

- **WHEN** the user clicks the "Cancel" button during a download
- **THEN** the download SHALL be interrupted
- **THEN** the card SHALL transition back to the "not downloaded" state
- **THEN** all other cards' download buttons SHALL be re-enabled

### Requirement: Delete Downloaded Model

The user SHALL be able to delete a downloaded model by clicking the "Delete" button. A confirmation dialog (`QMessageBox`) SHALL be displayed before deletion. Upon confirmation, the system SHALL call `ModelManager.delete_model()` and transition the card back to the "not downloaded" state. A `model_deleted` signal SHALL be emitted to notify dependent pages.

#### Scenario: Delete with confirmation

- **WHEN** the user clicks "Delete" on a downloaded model card
- **THEN** a confirmation dialog SHALL be displayed

#### Scenario: Confirm deletion

- **WHEN** the user confirms the deletion in the dialog
- **THEN** the model file SHALL be deleted via `ModelManager.delete_model()`
- **THEN** the card SHALL transition to the "not downloaded" state
- **THEN** a `model_deleted` signal SHALL be emitted

#### Scenario: Cancel deletion

- **WHEN** the user cancels the deletion dialog
- **THEN** the model SHALL remain downloaded and the card state SHALL not change

### Requirement: Cross-Page Refresh on Model State Change

When a model is downloaded or deleted on the Model Management page, the system SHALL emit a signal (`model_downloaded` or `model_deleted`) that the `SettingsWindow` connects to refresh the Voice page's ASR model dropdown and the LLM page's local model dropdown.

#### Scenario: Model downloaded triggers refresh

- **WHEN** a model download completes on the Model Management page
- **THEN** the Voice page's `refresh_asr_combo()` and the LLM page's `refresh_llm_combo()` SHALL be invoked

#### Scenario: Model deleted triggers refresh

- **WHEN** a model is deleted on the Model Management page
- **THEN** the Voice page's `refresh_asr_combo()` and the LLM page's `refresh_llm_combo()` SHALL be invoked

### Requirement: Theme-Aware Card Styling

Model cards SHALL adapt their visual styling (border color, background color, hover color) to the current application theme (light or dark). When the theme changes, all visible cards SHALL update their stylesheet accordingly.

#### Scenario: Light theme card appearance

- **WHEN** the application theme is set to light
- **THEN** model cards SHALL display with light background, light border color, and appropriate hover effect

#### Scenario: Dark theme card appearance

- **WHEN** the application theme is set to dark
- **THEN** model cards SHALL display with dark background, dark border color, and appropriate hover effect
