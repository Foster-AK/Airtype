## ADDED Requirements

### Requirement: PyTorch CUDA Inference

The system SHALL implement `QwenPyTorchEngine` to load the Qwen3-ASR model via PyTorch with CUDA bfloat16 precision for NVIDIA GPU inference. The engine SHALL conform to the ASREngine Protocol.

#### Scenario: CUDA recognition

- **WHEN** an NVIDIA GPU with CUDA is available and the PyTorch engine is loaded
- **THEN** inference SHALL execute on the GPU with bfloat16 precision

#### Scenario: No CUDA available

- **WHEN** `torch.cuda.is_available()` returns `False`
- **THEN** the engine SHALL NOT register in the `ASREngineRegistry`

### Requirement: Vulkan Inference via chatllm.cpp

The system SHALL implement `QwenVulkanEngine` to load the Qwen3-ASR GGUF quantized model via chatllm.cpp with the Vulkan backend for cross-vendor GPU inference (NVIDIA, AMD, Intel).

#### Scenario: Vulkan recognition

- **WHEN** a Vulkan-compatible GPU is available and chatllm.cpp bindings are installed
- **THEN** inference SHALL execute through the Vulkan backend

### Requirement: Optional Dependencies with Graceful Degradation

Both GPU engines SHALL be optional. If the required packages (`torch` for CUDA, `chatllm.cpp` for Vulkan) are not installed, the corresponding engine SHALL NOT register in the `ASREngineRegistry` and SHALL NOT raise an error.

#### Scenario: torch package missing

- **WHEN** the `torch` package is not installed
- **THEN** `QwenPyTorchEngine` SHALL NOT register and SHALL NOT produce an import error

### Requirement: GPU Engine Registration

The PyTorch engine SHALL register as `"qwen3-pytorch-cuda"` in the `ASREngineRegistry`. The Vulkan engine SHALL register as `"qwen3-vulkan"`.

#### Scenario: Both engines available

- **WHEN** both `torch+CUDA` and `chatllm.cpp` are installed
- **THEN** both `"qwen3-pytorch-cuda"` and `"qwen3-vulkan"` SHALL be available in the registry

## Requirements

### Requirement: PyTorch CUDA Inference

The system SHALL implement `QwenPyTorchEngine` to load the Qwen3-ASR model via PyTorch with CUDA bfloat16 precision for NVIDIA GPU inference. The engine SHALL conform to the ASREngine Protocol.

#### Scenario: CUDA recognition

- **WHEN** an NVIDIA GPU with CUDA is available and the PyTorch engine is loaded
- **THEN** inference SHALL execute on the GPU with bfloat16 precision

#### Scenario: No CUDA available

- **WHEN** `torch.cuda.is_available()` returns `False`
- **THEN** the engine SHALL NOT register in the `ASREngineRegistry`

---
### Requirement: Vulkan Inference via chatllm.cpp

The system SHALL implement `QwenVulkanEngine` to load the Qwen3-ASR GGUF quantized model via chatllm.cpp with the Vulkan backend for cross-vendor GPU inference (NVIDIA, AMD, Intel).

#### Scenario: Vulkan recognition

- **WHEN** a Vulkan-compatible GPU is available and chatllm.cpp bindings are installed
- **THEN** inference SHALL execute through the Vulkan backend

---
### Requirement: Optional Dependencies with Graceful Degradation

Both GPU engines SHALL be optional. If the required packages (`torch` for CUDA, `chatllm.cpp` for Vulkan) are not installed, the corresponding engine SHALL NOT register in the `ASREngineRegistry` and SHALL NOT raise an error.

#### Scenario: torch package missing

- **WHEN** the `torch` package is not installed
- **THEN** `QwenPyTorchEngine` SHALL NOT register and SHALL NOT produce an import error

---
### Requirement: GPU Engine Registration

The PyTorch engine SHALL register as `"qwen3-pytorch-cuda"` in the `ASREngineRegistry`. The Vulkan engine SHALL register as `"qwen3-vulkan"`.

#### Scenario: Both engines available

- **WHEN** both `torch+CUDA` and `chatllm.cpp` are installed
- **THEN** both `"qwen3-pytorch-cuda"` and `"qwen3-vulkan"` SHALL be available in the registry
