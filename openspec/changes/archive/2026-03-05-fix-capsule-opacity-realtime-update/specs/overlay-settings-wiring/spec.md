## ADDED Requirements

### Requirement: Overlay appearance signals are connected at startup

The application SHALL call `settings_window.connect_overlay(overlay)` during UI initialization, after both `CapsuleOverlay` and `SettingsWindow` have been instantiated.

#### Scenario: Opacity slider adjusted in settings panel

- **WHEN** the user drags the capsule opacity slider in the Appearance settings page
- **THEN** the capsule window SHALL update its background alpha immediately without requiring an app restart

#### Scenario: Theme changed in settings panel

- **WHEN** the user changes the theme (light / dark / system) in the Appearance settings page
- **THEN** the capsule window SHALL apply the new QPalette immediately without requiring an app restart

#### Scenario: Capsule position changed in settings panel

- **WHEN** the user changes the capsule position in the Appearance settings page
- **THEN** the capsule window SHALL move to the new position immediately without requiring an app restart

#### Scenario: App restarts after appearance change

- **WHEN** the user adjusts any appearance setting and then restarts the app
- **THEN** the app SHALL load the previously saved setting and display the capsule with the correct appearance
