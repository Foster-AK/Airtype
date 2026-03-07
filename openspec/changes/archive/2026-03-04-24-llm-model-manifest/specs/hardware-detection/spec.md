## ADDED Requirements

### Requirement: LLM Inference Recommendation

The `HardwareDetector` SHALL provide a `recommend_llm()` method that returns the recommended local LLM model and backend based on detected hardware capabilities. The recommendation SHALL follow this decision tree: NVIDIA GPU (VRAM≥8GB) → qwen2.5-7b-instruct-q4_k_m, backend="local"; NVIDIA GPU (VRAM≥4GB) → qwen2.5-3b-instruct-q4_k_m, backend="local"; AMD/Intel GPU → qwen2.5-1.5b-instruct-q4_k_m, backend="local"; CPU-only (RAM≥8GB) → qwen2.5-1.5b-instruct-q4_k_m, backend="local"; CPU-only (RAM<8GB) → model=None, backend="disabled".

#### Scenario: Recommend Large LLM for High-VRAM NVIDIA GPU

- **WHEN** the hardware has an NVIDIA GPU with VRAM ≥ 8GB
- **THEN** `recommend_llm()` SHALL return `model="qwen2.5-7b-instruct-q4_k_m"`, `backend="local"`

#### Scenario: Recommend Medium LLM for Mid-Range NVIDIA GPU

- **WHEN** the hardware has an NVIDIA GPU with VRAM ≥ 4GB and < 8GB
- **THEN** `recommend_llm()` SHALL return `model="qwen2.5-3b-instruct-q4_k_m"`, `backend="local"`

#### Scenario: Recommend Small LLM for AMD or Intel GPU

- **WHEN** the hardware has an AMD or Intel GPU (any VRAM)
- **THEN** `recommend_llm()` SHALL return `model="qwen2.5-1.5b-instruct-q4_k_m"`, `backend="local"`

#### Scenario: Recommend Small LLM for CPU-Only with Sufficient RAM

- **WHEN** the hardware has no discrete GPU and total RAM ≥ 8GB
- **THEN** `recommend_llm()` SHALL return `model="qwen2.5-1.5b-instruct-q4_k_m"`, `backend="local"`, and `warning="approaching_timeout_cpu"`

#### Scenario: Recommend Disabled for Low-End CPU-Only

- **WHEN** the hardware has no discrete GPU and total RAM < 8GB
- **THEN** `recommend_llm()` SHALL return `model=None`, `backend="disabled"`
