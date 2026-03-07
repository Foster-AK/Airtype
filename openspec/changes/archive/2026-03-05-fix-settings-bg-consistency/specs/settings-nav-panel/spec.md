## MODIFIED Requirements

### Requirement: Navigation Panel Selection Style

The settings window navigation panel SHALL display the selected item as an inset pill shape with a distinct background colour and contrasting text colour.

The selected item SHALL have horizontal margin (`margin: 2px 8px`) and border radius (`border-radius: 6px`) so that the highlight does not span the full panel width.

The selected item background colour SHALL be `#0a84ff` and the text colour SHALL be white (`#ffffff`).

#### Scenario: Selected item appearance

- **WHEN** a navigation item is selected
- **THEN** the item background SHALL be `#0a84ff` and the text colour SHALL be white (`#ffffff`)
- **THEN** the highlighted area SHALL NOT span the full width of the navigation panel
- **THEN** the highlighted area SHALL have rounded corners with a radius of `6px`

## ADDED Requirements

### Requirement: Navigation Panel Hover State

The settings window navigation panel SHALL display a subtle hover background on unselected items when the pointer is over them, providing interactive feedback.

#### Scenario: Pointer over unselected item

- **WHEN** the user moves the pointer over a navigation item that is NOT currently selected
- **THEN** the item SHALL display a translucent hover background (`rgba(0, 0, 0, 0.06)`)

#### Scenario: Pointer over selected item

- **WHEN** the user moves the pointer over the currently selected navigation item
- **THEN** the hover background SHALL NOT be applied; the selection style SHALL remain unchanged
