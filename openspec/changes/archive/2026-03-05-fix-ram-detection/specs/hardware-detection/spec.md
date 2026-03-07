## ADDED Requirements

### Requirement: RAM Detection with Reliable Fallback Chain

The system SHALL detect total physical RAM using a prioritized fallback chain to ensure correctness across all supported platforms. The fallback chain SHALL be: (1) psutil (required dependency); (2) ctypes GlobalMemoryStatusEx on Windows; (3) sysctl on macOS; (4) /proc/meminfo on Linux. The system SHALL NOT rely on wmic for RAM detection. psutil SHALL be declared as a formal package dependency.

#### Scenario: RAM Detection via psutil

- **WHEN** psutil is installed (as a formal dependency)
- **THEN** `_get_total_ram_mb()` SHALL return `psutil.virtual_memory().total // (1024 * 1024)` without triggering any WARNING

#### Scenario: RAM Detection via ctypes on Windows (psutil unavailable)

- **WHEN** psutil is not available and the platform is Windows
- **THEN** `_get_total_ram_mb()` SHALL call `kernel32.GlobalMemoryStatusEx` via ctypes and return the correct total physical RAM in MB

#### Scenario: RAM Detection Fallback Warning

- **WHEN** all detection methods fail
- **THEN** `_get_total_ram_mb()` SHALL log a WARNING and return 4096 as the assumed value

#### Scenario: Debug Log on Fallback Failure

- **WHEN** any individual fallback method fails
- **THEN** the system SHALL log the specific failure reason at DEBUG level before attempting the next method
