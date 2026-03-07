## ADDED Requirements

### Requirement: Hardware Recommendation Warning in LLM Settings UI

The `SettingsLlmPage` SHALL call `HardwareDetector.recommend_llm()` on initialization and display a visible warning label when the result contains `warning="approaching_timeout_cpu"`. The warning SHALL inform the user that local LLM inference on CPU-only hardware is at risk of exceeding the 3-second timeout and SHALL suggest switching to API mode or a smaller model.

#### Scenario: Showing CPU Timeout Warning

- **WHEN** `HardwareDetector.recommend_llm()` returns `warning="approaching_timeout_cpu"`
- **THEN** `SettingsLlmPage` SHALL display a yellow warning label: "⚠ 偵測到 CPU-only 環境，本機 LLM 可能接近 3 秒逾時限制，建議使用 API 模式"

#### Scenario: No Warning for GPU Hardware

- **WHEN** `HardwareDetector.recommend_llm()` returns `warning=None` (or no warning field)
- **THEN** `SettingsLlmPage` SHALL NOT display the CPU timeout warning label

#### Scenario: HardwareDetector Unavailable

- **WHEN** `HardwareDetector` raises an exception or is unavailable (e.g., import error)
- **THEN** `SettingsLlmPage` SHALL silently suppress the error and display no warning
