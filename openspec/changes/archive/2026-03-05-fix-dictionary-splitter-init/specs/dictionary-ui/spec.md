## ADDED Requirements

### Requirement: Dictionary Page Layout Uses QHBoxLayout

The dictionary settings page SHALL use a `QHBoxLayout` to arrange the dictionary set panel (left) and the hot words / replace rules panel (right). The page SHALL NOT use a resizable splitter (`QSplitter`) for this layout. The two panels SHALL be displayed adjacent to each other with no empty space between them upon first display.

#### Scenario: First display with no prior user interaction

- **WHEN** the user opens the settings panel and navigates to the dictionary page
- **THEN** the dictionary set panel (left) and hot words panel (right) SHALL be visually adjacent with no gap between them

### Requirement: Dictionary Set Panel Uses QGroupBox

The dictionary set panel SHALL be presented as a `QGroupBox` with a title, consistent with the hot words and replace rules panels on the right side. The panel SHALL have a fixed width of 160px.

#### Scenario: Visual consistency with other panels

- **WHEN** the dictionary page is displayed
- **THEN** all three panels (dictionary sets, hot words, replace rules) SHALL be rendered as `QGroupBox` elements with titles
