## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Apple Silicon Detection

The `HardwareDetector` SHALL detect whether the system is running on macOS with Apple Silicon by checking `sys.platform == "darwin"` and `platform.machine() == "arm64"`. The `SystemCapabilities` dataclass SHALL include an `is_apple_silicon: bool` field.

#### Scenario: Detect Apple Silicon Mac

- **WHEN** `HardwareDetector.assess()` is called on a MacBook Air M1
- **THEN** the result SHALL have `is_apple_silicon = True`

#### Scenario: Detect non-Apple-Silicon system

- **WHEN** `HardwareDetector.assess()` is called on a Windows x86_64 system
- **THEN** the result SHALL have `is_apple_silicon = False`
