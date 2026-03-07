## ADDED Requirements

### Requirement: Performance Benchmark Suite

The system SHALL include a benchmark suite that measures the following metrics: hotkey response time (<100 ms), waveform frame rate (≥30 FPS), ASR batch latency (<2 s for 10-second audio on GPU), end-to-end latency without LLM (<3 s), and end-to-end latency with LLM (<6 s).

#### Scenario: Hotkey Response Benchmark

- **WHEN** the hotkey response benchmark is executed
- **THEN** the measured latency SHALL be less than 100 ms

### Requirement: Lazy Loading and On-Demand Model Management

ASR and LLM models SHALL be loaded only on first use. Idle models SHALL be unloaded after a configurable timeout (default 5 minutes) to free RAM.

#### Scenario: Unload Model After Idle Timeout

- **WHEN** an ASR model has not been used for 5 minutes
- **THEN** the model SHALL be unloaded and RAM SHALL be released

### Requirement: Resource Usage Targets

Idle CPU usage SHALL be <1%. Idle RAM usage SHALL be <150 MB. RAM usage during recording SHALL be <200 MB.

#### Scenario: Measure Idle Resource Usage

- **WHEN** the application is in the idle state (not recording)
- **THEN** CPU usage SHALL be <1% and RAM usage SHALL be <150 MB

### Requirement: Performance Testing with pytest-benchmark

Performance tests SHALL use `pytest-benchmark` for reproducible measurements and regression tracking.

#### Scenario: Run Benchmarks

- **WHEN** `pytest tests/test_performance.py --benchmark-only` is executed
- **THEN** benchmark results SHALL be displayed as a statistical summary
