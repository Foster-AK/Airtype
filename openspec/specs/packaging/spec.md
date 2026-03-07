# packaging Specification

## Purpose

TBD - created by archiving change '22-packaging-release'. Update Purpose after archive.

## Requirements

### Requirement: Single Executable via PyInstaller

The system SHALL use PyInstaller as the primary build tool to produce a single executable. The executable SHALL bundle all Python dependencies and embedded model files.

#### Scenario: Build Executable

- **WHEN** the build script is executed
- **THEN** a single executable SHALL be produced that runs without requiring a Python installation

---
### Requirement: Windows NSIS Installer

A Windows NSIS installer SHALL be provided that installs the application, creates Start Menu shortcuts, and supports uninstallation.

#### Scenario: Install on Windows

- **WHEN** the user runs the NSIS installer on Windows
- **THEN** the application SHALL be installed and accessible from the Start Menu

---
### Requirement: macOS DMG

A macOS DMG image SHALL be provided that offers a drag-to-Applications installation experience.

#### Scenario: Install on macOS

- **WHEN** the user opens the DMG and drags Airtype to the Applications folder
- **THEN** the application SHALL be launchable from the Applications folder

---
### Requirement: Linux AppImage

A Linux AppImage SHALL be provided that runs on most Linux distributions without installation.

#### Scenario: Run AppImage on Linux

- **WHEN** the user downloads the AppImage and grants execute permission
- **THEN** the application SHALL run without requiring additional dependencies

---
### Requirement: Platform-Specific Build Scripts

Each platform SHALL have a dedicated build script under the `build/` directory: `build_windows.bat`, `build_macos.sh`, and `build_linux.sh`.

#### Scenario: Execute Build Script

- **WHEN** a platform build script is executed
- **THEN** it SHALL produce a distributable package for that platform

---
### Requirement: Update Check via HTTPS Manifest

The application SHALL fetch a version manifest JSON over HTTPS to check for updates. Automatic download or installation SHALL NOT be performed — notification only.

#### Scenario: New Version Available

- **WHEN** the version manifest indicates a newer version is available
- **THEN** the About page SHALL display an update notification with a download link
