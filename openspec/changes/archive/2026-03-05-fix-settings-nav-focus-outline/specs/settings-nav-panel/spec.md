## ADDED Requirements

### Requirement: Navigation Panel Focus Indicator

The settings window navigation panel (QListWidget) SHALL NOT display a platform-default focus rectangle (outline) when an item receives focus or is clicked.

#### Scenario: Click navigation item

- **WHEN** the user clicks a navigation item in the settings window
- **THEN** the item is selected with the active selection style and no focus outline is drawn around it

#### Scenario: Keyboard navigation

- **WHEN** the user navigates items using keyboard arrow keys
- **THEN** the focused item SHALL NOT display a dashed or dotted outline border

### Requirement: Navigation Panel Selection Style

The settings window navigation panel SHALL display the selected item with a distinct background colour and contrasting text colour.

#### Scenario: Selected item appearance

- **WHEN** a navigation item is selected
- **THEN** the item background SHALL be `#0a84ff` and the text colour SHALL be white (`#ffffff`)
