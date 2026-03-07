## ADDED Requirements

### Requirement: Clipboard Backup

The system SHALL save the current clipboard content before injection. The backup SHALL capture the text content via pyperclip. If the clipboard is empty or contains non-text content, the backup SHALL be treated as an empty string.

#### Scenario: Back Up Existing Clipboard Text

- **WHEN** injection begins and the clipboard contains "original text"
- **THEN** the system SHALL store "original text" as the backup value before modifying the clipboard

#### Scenario: Back Up Empty Clipboard

- **WHEN** injection begins and the clipboard is empty
- **THEN** the system SHALL store an empty string as the backup value and continue with injection

### Requirement: Text Injection via Paste

The system SHALL write the recognized text to the clipboard, restore focus to the target window via the FocusManager from 04-hotkey-focus, wait 50ms for focus to stabilize, then simulate Ctrl+V (or Cmd+V on macOS) to paste the text at the cursor position.

#### Scenario: Inject Recognized Chinese Text

- **WHEN** the ASR engine produces recognized text "你好世界"
- **THEN** the system SHALL write "你好世界" to the clipboard, restore focus to the target window, and simulate a paste so that the text appears at the cursor position in the target application

#### Scenario: Inject into Active Application

- **WHEN** injection is triggered and the target application is a text editor
- **THEN** the recognized text SHALL appear at the cursor position in that text editor

### Requirement: Clipboard Restore

The system SHALL restore the original clipboard content after injection completes, with a configurable delay (default 150ms) to allow the target application to process the paste. The delay SHALL be configurable via the `general.clipboard_restore_delay_ms` configuration field.

#### Scenario: Restore Original Clipboard After Injection

- **WHEN** injection completes and the original clipboard contained "original text"
- **THEN** after the configured delay (default 150ms), the clipboard SHALL contain "original text" again

#### Scenario: Restore Empty Clipboard After Injection

- **WHEN** injection completes and the original clipboard was empty
- **THEN** after the configured delay, the clipboard SHALL be set to an empty string

### Requirement: Injection Timing

The complete injection cycle (backup → write → focus → paste → wait → restore) SHALL complete within 300ms under normal operating conditions. The timing breakdown SHALL be approximately: clipboard backup ~5ms, clipboard write ~5ms, focus restore ~25ms + 50ms wait, paste simulation ~5ms, restore delay 150ms.

#### Scenario: Measure Injection Cycle Time

- **WHEN** the complete injection cycle is executed on a normally loaded system
- **THEN** the total elapsed time from backup start to restore completion SHALL be less than 300ms

### Requirement: Cross-Platform Paste Simulation

Paste simulation SHALL use Ctrl+V on Windows and Linux, and Cmd+V on macOS. The platform SHALL be detected at runtime via `sys.platform`.

#### Scenario: Paste on Windows

- **WHEN** injection is executed on a Windows system
- **THEN** the system SHALL simulate Ctrl+V using pyautogui

#### Scenario: Paste on macOS

- **WHEN** injection is executed on a macOS system
- **THEN** the system SHALL simulate Cmd+V using pyautogui

#### Scenario: Paste on Linux

- **WHEN** injection is executed on a Linux system
- **THEN** the system SHALL simulate Ctrl+V using pyautogui
