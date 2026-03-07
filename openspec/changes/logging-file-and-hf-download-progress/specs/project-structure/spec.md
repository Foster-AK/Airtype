## MODIFIED Requirements

### Requirement: Structured Logging

The application SHALL configure Python standard library `logging` at startup with the format `[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s`. The log level SHALL be configurable via `general.log_level` in the configuration file, with supported values: DEBUG, INFO, WARNING, ERROR. In addition to the console handler (`sys.stderr`), the application SHALL write logs to a rotating file at `~/.airtype/logs/airtype.log` using `RotatingFileHandler` with a maximum file size of 5 MB and 3 backup files. The file handler SHALL always use DEBUG level regardless of the configured log level.

#### Scenario: Default log level

- **WHEN** the application starts with default settings
- **THEN** the log level SHALL be set to INFO

#### Scenario: Custom log level

- **WHEN** the configuration file general section contains `"log_level": "DEBUG"`
- **THEN** the application SHALL set the root logger level to DEBUG

#### Scenario: Log file creation

- **WHEN** the application starts for the first time
- **THEN** the directory `~/.airtype/logs/` SHALL be created if it does not exist and logs SHALL be written to `~/.airtype/logs/airtype.log`

#### Scenario: Log file rotation

- **WHEN** the log file exceeds 5 MB
- **THEN** the file SHALL be rotated and up to 3 backup files SHALL be retained

#### Scenario: Log file handler failure

- **WHEN** the log file cannot be created due to disk full or permission error
- **THEN** the application SHALL print a warning to stderr and continue startup without file logging

#### Scenario: Log file available in packaged application

- **WHEN** the application is packaged with PyInstaller using `console=False`
- **THEN** logs SHALL still be written to `~/.airtype/logs/airtype.log` regardless of console visibility
