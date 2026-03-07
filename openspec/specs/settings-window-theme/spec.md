# settings-window-theme Specification

## Purpose

TBD - created by archiving change 'fix-settings-bg-consistency'. Update Purpose after archive.

## Requirements

### Requirement: Settings Window Light Theme Background

The settings window SHALL display explicit, consistent background colours in light and system themes, overriding any OS-default window palette colour.

The navigation panel background colour SHALL be `#fafafa`.
The content area background colour SHALL be `#ffffff`.

#### Scenario: Light theme applied

- **WHEN** the settings window is opened with theme set to `light`
- **THEN** the navigation panel background SHALL be `#fafafa`
- **THEN** the content area background SHALL be `#ffffff`

#### Scenario: System theme applied

- **WHEN** the settings window is opened with theme set to `system`
- **THEN** the navigation panel background SHALL be `#fafafa`
- **THEN** the content area background SHALL be `#ffffff`

---
### Requirement: Settings Window Dark Theme Background

The settings window SHALL display explicit dark background colours in dark theme.

The navigation panel background colour SHALL be `#252525`.
The content area background colour SHALL be `#2d2d2d`.

#### Scenario: Dark theme applied

- **WHEN** the settings window is opened with theme set to `dark`
- **THEN** the navigation panel background SHALL be `#252525`
- **THEN** the content area background SHALL be `#2d2d2d`

---
### Requirement: Settings Window Theme Change Response

The settings window background colours SHALL update immediately when the theme is changed via the Appearance settings page, without requiring the window to be closed and reopened.

#### Scenario: Theme switched from light to dark

- **WHEN** the user changes the theme to `dark` in the Appearance page
- **THEN** the navigation panel background SHALL update to `#252525` immediately
- **THEN** the content area background SHALL update to `#2d2d2d` immediately

#### Scenario: Theme switched from dark to light

- **WHEN** the user changes the theme to `light` in the Appearance page
- **THEN** the navigation panel background SHALL update to `#fafafa` immediately
- **THEN** the content area background SHALL update to `#ffffff` immediately
