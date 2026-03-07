## ADDED Requirements

### Requirement: Appearance Settings Page

The settings panel SHALL provide an Appearance page containing: theme options (light/dark/system), capsule position dropdown, capsule scale slider (80–150%), capsule opacity slider (50–100%), waveform style dropdown (bars/wave/dots), waveform color picker, show status text toggle, and show live preview toggle.

#### Scenario: Switch Theme to Dark

- **WHEN** the user selects the "Dark" theme
- **THEN** the application UI SHALL immediately switch to dark mode

#### Scenario: Adjust Capsule Opacity

- **WHEN** the user sets the capsule opacity to 70%
- **THEN** the floating capsule SHALL immediately update to 70% opacity
