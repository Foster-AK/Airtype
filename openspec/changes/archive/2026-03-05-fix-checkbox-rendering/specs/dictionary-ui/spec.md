## MODIFIED Requirements

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
