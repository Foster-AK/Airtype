# Spec: System Tray

## Purpose

This capability defines the system tray integration for Airtype. It covers the stateful QSystemTrayIcon with dynamic state-driven icons, the right-click context menu with application actions, system notifications via QSystemTrayIcon.showMessage(), and close-to-tray window behavior to keep the application running in the background.

---

## Requirements

### Requirement: Stateful System Tray Icon

The system SHALL display a QSystemTrayIcon with a dynamic icon reflecting the application state (idle, listening, error).

#### Scenario: Icon Changes During Recording

- **WHEN** the application transitions to the LISTENING state
- **THEN** the system tray icon SHALL change to indicate that recording is in progress

---
### Requirement: Context Menu Actions

The system tray icon SHALL provide a right-click context menu containing: open settings, toggle voice input, current status display, and quit. The quit action SHALL exit the application.

#### Scenario: Open Settings from System Tray

- **WHEN** the user right-clicks the system tray icon and selects "Open Settings"
- **THEN** the settings panel SHALL be displayed

---
### Requirement: Notifications via showMessage

The system SHALL display a system notification after recognition completes when `general.notifications` is enabled. Notifications SHALL use `QSystemTrayIcon.showMessage()`.

#### Scenario: Notification After Recognition

- **WHEN** text is successfully injected and notifications are enabled
- **THEN** a system notification SHALL be displayed containing a summary of the injected text

---
### Requirement: Close to Tray Behavior

Closing any application window SHALL hide the window rather than quit the application. Only the "Quit" menu item SHALL exit the application.

#### Scenario: Close Settings Window

- **WHEN** the user closes the settings window via the X button
- **THEN** the window SHALL be hidden and the application SHALL continue running in the system tray
