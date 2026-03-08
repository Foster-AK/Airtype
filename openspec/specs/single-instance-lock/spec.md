# single-instance-lock Specification

## Purpose

TBD - created by archiving change 'single-instance-lock'. Update Purpose after archive.

## Requirements

### Requirement: Single Instance Enforcement

The application SHALL enforce that only one instance of Airtype runs at a time on the same user session. The enforcement mechanism SHALL use an OS-level file lock at `~/.airtype/airtype.lock` via `fcntl.flock` (Unix) or `msvcrt.locking` (Windows).

#### Scenario: First instance starts successfully

- **WHEN** the user launches Airtype and no other instance is running
- **THEN** the application SHALL acquire the file lock on `~/.airtype/airtype.lock`
- **THEN** the application SHALL proceed with normal startup (QApplication creation and component initialization)
- **THEN** the lock file SHALL contain the current process PID

#### Scenario: Second instance is rejected

- **WHEN** the user launches a second Airtype instance while the first is still running
- **THEN** the second instance SHALL fail to acquire the file lock
- **THEN** the second instance SHALL log a warning message indicating another instance is already running
- **THEN** the second instance SHALL exit with code 0 (normal exit)
- **THEN** the first instance SHALL remain unaffected

#### Scenario: Lock released on normal shutdown

- **WHEN** the running Airtype instance shuts down normally (via system tray quit or window close)
- **THEN** the file lock SHALL be released during the cleanup phase
- **THEN** a new instance SHALL be able to start successfully afterwards

#### Scenario: Lock released on crash

- **WHEN** the running Airtype instance terminates unexpectedly (crash, SIGKILL, Task Manager kill)
- **THEN** the OS SHALL automatically release the file lock (guaranteed by flock/msvcrt semantics)
- **THEN** a new instance SHALL be able to start successfully afterwards


<!-- @trace
source: single-instance-lock
updated: 2026-03-08
code:
  - airtype/__main__.py
tests:
  - tests/test_single_instance.py
  - tests/test_main.py
-->

---
### Requirement: Lock Directory Auto-Creation

The lock acquisition function SHALL create the `~/.airtype/` directory if it does not exist, because the lock is acquired before `AirtypeConfig.load()` which normally creates this directory.

#### Scenario: Fresh installation with no config directory

- **WHEN** the user launches Airtype for the first time and `~/.airtype/` does not exist
- **THEN** the lock acquisition function SHALL create `~/.airtype/` with `os.makedirs(exist_ok=True)`
- **THEN** the lock file SHALL be created and acquired successfully
- **THEN** normal startup SHALL proceed


<!-- @trace
source: single-instance-lock
updated: 2026-03-08
code:
  - airtype/__main__.py
tests:
  - tests/test_single_instance.py
  - tests/test_main.py
-->

---
### Requirement: Lock Timing in Startup Sequence

The instance lock SHALL be acquired after `setup_logging()` but before `AirtypeConfig.load()` and before `QApplication` creation, ensuring the logger is available for warning messages while preventing any resource initialization in duplicate instances.

#### Scenario: Lock acquired before QApplication

- **WHEN** the application starts the `main()` function
- **THEN** the lock acquisition SHALL occur after the initial `setup_logging("INFO")` call
- **THEN** the lock acquisition SHALL occur before `AirtypeConfig.load()`
- **THEN** if the lock fails, `sys.exit(0)` SHALL be called without creating any `QApplication` or initializing any component


<!-- @trace
source: single-instance-lock
updated: 2026-03-08
code:
  - airtype/__main__.py
tests:
  - tests/test_single_instance.py
  - tests/test_main.py
-->

---
### Requirement: Test Isolation for Instance Lock

The instance lock function SHALL be implemented as a standalone function `_acquire_instance_lock()` that returns a file object on success or `None` on failure, enabling test isolation via mocking.

#### Scenario: Existing main() tests remain unaffected

- **WHEN** running existing `test_main.py` tests that call `main()`
- **THEN** the `_acquire_instance_lock` function SHALL be patched to return a `MagicMock`
- **THEN** all existing tests SHALL pass without modification to their assertions

<!-- @trace
source: single-instance-lock
updated: 2026-03-08
code:
  - airtype/__main__.py
tests:
  - tests/test_single_instance.py
  - tests/test_main.py
-->