# Hardware Detection Spec

## Requirement: GPU Detection

The system SHALL detect the presence and type of GPU (NVIDIA, AMD, Intel) and its VRAM capacity. Detection SHALL use platform-appropriate methods (nvidia-smi, WMI, system_profiler, lspci).

### Scenario: NVIDIA GPU Detected

- **WHEN** an NVIDIA GPU is present
- **THEN** the detector SHALL return GPU vendor="nvidia", model name, and VRAM in MB

### Scenario: No GPU Detected

- **WHEN** no discrete GPU is available
- **THEN** the detector SHALL return GPU vendor=None

## Requirement: System Capability Assessment

The system SHALL assess CPU type, total RAM, and available disk space to determine system capabilities for ASR model selection.

### Scenario: Assess System

- **WHEN** `HardwareDetector.assess()` is called
- **THEN** it SHALL return a SystemCapabilities dataclass containing gpu_vendor, gpu_vram_mb, cpu_type, total_ram_mb, and available_disk_mb

## Requirement: Inference Path Recommendation

The system SHALL recommend the optimal ASR inference path based on detected hardware, following this decision tree: NVIDIA GPU (VRAM≥4GB) → PyTorch CUDA 1.7B; NVIDIA (VRAM≥2GB) → PyTorch CUDA 0.6B; AMD/Intel GPU → Vulkan 0.6B; CPU (RAM≥6GB) → OpenVINO INT8 0.6B; CPU (RAM<6GB) → sherpa-onnx SenseVoice.

### Scenario: Recommend NVIDIA GPU with 8GB VRAM

- **WHEN** the hardware has an NVIDIA GPU with 8GB VRAM
- **THEN** the recommendation SHALL be engine="qwen3-pytorch-cuda", model="qwen3-asr-1.7b"

### Scenario: Recommend CPU-Only with 8GB RAM

- **WHEN** the hardware has no GPU and has 8GB RAM
- **THEN** the recommendation SHALL be engine="qwen3-openvino", model="qwen3-asr-0.6b"

## Requirements

### Requirement: GPU Detection

The system SHALL detect the presence and type of GPU (NVIDIA, AMD, Intel) and its VRAM capacity. Detection SHALL use platform-appropriate methods (nvidia-smi, WMI, system_profiler, lspci).

#### Scenario: NVIDIA GPU Detected

- **WHEN** an NVIDIA GPU is present
- **THEN** the detector SHALL return GPU vendor="nvidia", model name, and VRAM in MB

#### Scenario: No GPU Detected

- **WHEN** no discrete GPU is available
- **THEN** the detector SHALL return GPU vendor=None

---
### Requirement: System Capability Assessment

The system SHALL assess CPU type, total RAM, and available disk space to determine system capabilities for ASR model selection.

#### Scenario: Assess System

- **WHEN** `HardwareDetector.assess()` is called
- **THEN** it SHALL return a SystemCapabilities dataclass containing gpu_vendor, gpu_vram_mb, cpu_type, total_ram_mb, and available_disk_mb

---
### Requirement: Inference Path Recommendation

The system SHALL recommend the optimal ASR inference path based on detected hardware, following this decision tree: Apple Silicon (macOS ARM64) → MLX 0.6B; NVIDIA GPU (VRAM≥4GB) → PyTorch CUDA 1.7B; NVIDIA (VRAM≥2GB) → PyTorch CUDA 0.6B; AMD/Intel GPU → Vulkan 0.6B; CPU (RAM≥6GB) → OpenVINO INT8 0.6B; CPU (RAM<6GB) → sherpa-onnx SenseVoice.

#### Scenario: Recommend Apple Silicon Mac

- **WHEN** the hardware is macOS with Apple Silicon (ARM64) CPU
- **THEN** the recommendation SHALL be engine="qwen3-mlx", model="qwen3-asr-0.6b"

#### Scenario: Recommend NVIDIA GPU with 8GB VRAM

- **WHEN** the hardware has an NVIDIA GPU with 8GB VRAM
- **THEN** the recommendation SHALL be engine="qwen3-pytorch-cuda", model="qwen3-asr-1.7b"

#### Scenario: Recommend CPU-Only with 8GB RAM

- **WHEN** the hardware has no GPU and has 8GB RAM
- **THEN** the recommendation SHALL be engine="qwen3-openvino", model="qwen3-asr-0.6b"


<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->

---
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

---
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

---
### Requirement: Apple Silicon Detection

The `HardwareDetector` SHALL detect whether the system is running on macOS with Apple Silicon by checking `sys.platform == "darwin"` and `platform.machine() == "arm64"`. The `SystemCapabilities` dataclass SHALL include an `is_apple_silicon: bool` field.

#### Scenario: Detect Apple Silicon Mac

- **WHEN** `HardwareDetector.assess()` is called on a MacBook Air M1
- **THEN** the result SHALL have `is_apple_silicon = True`

#### Scenario: Detect non-Apple-Silicon system

- **WHEN** `HardwareDetector.assess()` is called on a Windows x86_64 system
- **THEN** the result SHALL have `is_apple_silicon = False`

<!-- @trace
source: asr-qwen-mlx
updated: 2026-03-20
code:
  - CLAUDE.md
-->