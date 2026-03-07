# settings-nav-panel Specification

## Purpose

TBD - created by archiving change 'fix-settings-nav-focus-outline'. Update Purpose after archive.

## Requirements

### Requirement: Navigation Panel Focus Indicator

The settings window navigation panel (QListWidget) SHALL NOT display a platform-default focus rectangle (outline) when an item receives focus or is clicked.

#### Scenario: Click navigation item

- **WHEN** the user clicks a navigation item in the settings window
- **THEN** the item is selected with the active selection style and no focus outline is drawn around it

#### Scenario: Keyboard navigation

- **WHEN** the user navigates items using keyboard arrow keys
- **THEN** the focused item SHALL NOT display a dashed or dotted outline border

---
### Requirement: Navigation Panel Selection Style

The settings window navigation panel SHALL display the selected item as an inset pill shape with a distinct background colour and contrasting text colour.

The selected item SHALL have horizontal margin (`margin: 2px 8px`) and border radius (`border-radius: 6px`) so that the highlight does not span the full panel width.

The selected item background colour SHALL be `#0a84ff` and the text colour SHALL be white (`#ffffff`).

#### Scenario: Selected item appearance

- **WHEN** a navigation item is selected
- **THEN** the item background SHALL be `#0a84ff` and the text colour SHALL be white (`#ffffff`)
- **THEN** the highlighted area SHALL NOT span the full width of the navigation panel
- **THEN** the highlighted area SHALL have rounded corners with a radius of `6px`

---
### Requirement: Navigation Panel Hover State

The settings window navigation panel SHALL display a subtle hover background on unselected items when the pointer is over them, providing interactive feedback.

#### Scenario: Pointer over unselected item

- **WHEN** the user moves the pointer over a navigation item that is NOT currently selected
- **THEN** the item SHALL display a translucent hover background (`rgba(0, 0, 0, 0.06)`)

#### Scenario: Pointer over selected item

- **WHEN** the user moves the pointer over the currently selected navigation item
- **THEN** the hover background SHALL NOT be applied; the selection style SHALL remain unchanged

---
### Requirement: Model Management Navigation Item

The settings window navigation panel SHALL include a "Model Management" item positioned after the "Voice / ASR" item (index 2). The total number of navigation items SHALL be 8. All page index constants (`PAGE_*`) for pages after the new item SHALL be incremented by 1.

#### Scenario: Navigation item visible

- **WHEN** the settings window is opened
- **THEN** the navigation panel SHALL display "Model Management" as the third item (index 2)
- **THEN** the total number of navigation items SHALL be 8

#### Scenario: Navigate to model management page

- **WHEN** the user clicks the "Model Management" navigation item
- **THEN** the content area SHALL display the Model Management settings page
