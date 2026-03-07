## ADDED Requirements

### Requirement: Model Management Navigation Item

The settings window navigation panel SHALL include a "Model Management" item positioned after the "Voice / ASR" item (index 2). The total number of navigation items SHALL be 8. All page index constants (`PAGE_*`) for pages after the new item SHALL be incremented by 1.

#### Scenario: Navigation item visible

- **WHEN** the settings window is opened
- **THEN** the navigation panel SHALL display "Model Management" as the third item (index 2)
- **THEN** the total number of navigation items SHALL be 8

#### Scenario: Navigate to model management page

- **WHEN** the user clicks the "Model Management" navigation item
- **THEN** the content area SHALL display the Model Management settings page
