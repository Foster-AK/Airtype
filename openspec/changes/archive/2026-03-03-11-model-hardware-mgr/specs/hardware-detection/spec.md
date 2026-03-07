## ADDED Requirements

### Requirement: GPU Detection

The system SHALL detect the presence and type of GPU (NVIDIA, AMD, Intel) and its VRAM capacity. Detection SHALL use platform-appropriate methods (nvidia-smi, WMI, system_profiler, lspci).

#### Scenario: NVIDIA GPU Detected

- **WHEN** an NVIDIA GPU is present
- **THEN** the detector SHALL return GPU vendor="nvidia", model name, and VRAM in MB

#### Scenario: No GPU Detected

- **WHEN** no discrete GPU is available
- **THEN** the detector SHALL return GPU vendor=None

### Requirement: System Capability Assessment

The system SHALL assess CPU type, total RAM, and available disk space to determine system capabilities for ASR model selection.

#### Scenario: Assess System

- **WHEN** `HardwareDetector.assess()` is called
- **THEN** it SHALL return a SystemCapabilities dataclass containing gpu_vendor, gpu_vram_mb, cpu_type, total_ram_mb, and available_disk_mb

### Requirement: Inference Path Recommendation

The system SHALL recommend the optimal ASR inference path based on detected hardware, following this decision tree: NVIDIA GPU (VRAM≥4GB) → PyTorch CUDA 1.7B; NVIDIA (VRAM≥2GB) → PyTorch CUDA 0.6B; AMD/Intel GPU → Vulkan 0.6B; CPU (RAM≥6GB) → OpenVINO INT8 0.6B; CPU (RAM<6GB) → sherpa-onnx SenseVoice.

#### Scenario: Recommend NVIDIA GPU with 8GB VRAM

- **WHEN** the hardware has an NVIDIA GPU with 8GB VRAM
- **THEN** the recommendation SHALL be engine="qwen3-pytorch-cuda", model="qwen3-asr-1.7b"

#### Scenario: Recommend CPU-Only with 8GB RAM

- **WHEN** the hardware has no GPU and has 8GB RAM
- **THEN** the recommendation SHALL be engine="qwen3-openvino", model="qwen3-asr-0.6b"
