# Spec: settings-about

## Overview

About page within the Settings Panel. Displays version and system information, installed models, license details, and provides update checking, issue reporting, and diagnostics export actions.

## Requirements

### Requirement: About Page

The settings panel SHALL provide an About page displaying: version information, system information (OS, CPU, RAM, GPU), list of installed models, license information, a check for updates button, a report issue link, and an export diagnostics button.

#### Scenario: Check for Updates

- **WHEN** the user clicks "Check for Updates"
- **THEN** the system SHALL query the version manifest and SHALL display whether an update is available

#### Scenario: Export Diagnostics

- **WHEN** the user clicks "Export Diagnostics"
- **THEN** the system SHALL create a diagnostics bundle (system info, config, log excerpts) for use in bug reporting
