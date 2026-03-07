# Spec: NumPy Preprocessor

## Purpose

Provides pure-NumPy audio feature extraction (128-band log-Mel spectrogram) and BPE prompt tokenization for the Qwen3-ASR pipeline. Eliminates runtime dependencies on PyTorch, torchaudio, and librosa by using precomputed filterbank and token ID files.

## Requirements

### Requirement: Mel Spectrogram Extraction

The system SHALL extract 128-band log-Mel spectrogram features from 16kHz mono PCM audio using pure NumPy (STFT with a Hanning window, Mel filterbank, and log scaling). The implementation SHALL NOT depend on PyTorch, torchaudio, or librosa.

#### Scenario: Extract Features from Audio

- **WHEN** processing a 3-second 16kHz mono float32 numpy array
- **THEN** the system SHALL return a 2D numpy log-Mel spectrogram feature array containing 128 frequency bands

#### Scenario: No PyTorch Dependency

- **WHEN** the preprocessor module is imported
- **THEN** torch, torchaudio, and librosa SHALL NOT be imported

---
### Requirement: Precomputed Mel Filterbank

The system SHALL load the Mel filter matrix from a bundled `models/precomputed/mel_filters.npy` file. This file SHALL be pregenerated from the Qwen3-ASR model configuration.

#### Scenario: Load Filterbank

- **WHEN** the preprocessor is initialized
- **THEN** `mel_filters.npy` SHALL be loaded and used for Mel spectrogram computation

#### Scenario: Filter File Missing

- **WHEN** `mel_filters.npy` is missing
- **THEN** the system SHALL raise a FileNotFoundError with a descriptive message

---
### Requirement: BPE Prompt Tokenization

The system SHALL load preextracted BPE prompt token IDs from `models/precomputed/prompt_template.json` and prepend them to model inputs. No tokenizer library SHALL be required at runtime.

#### Scenario: Load Prompt Template

- **WHEN** the preprocessor is initialized
- **THEN** token IDs SHALL be loaded from `prompt_template.json`

#### Scenario: Prepend Tokens to Input

- **WHEN** preparing audio features for Qwen3-ASR
- **THEN** the prompt token IDs SHALL be prepended to the input sequence

---
### Requirement: Numerical Precision

The Mel spectrogram output produced by the NumPy implementation SHALL be within a tolerance of 1e-4 compared to the output of the PyTorch reference implementation when processing the same input audio.

#### Scenario: Precision Validation

- **WHEN** the same audio is processed by both the NumPy and PyTorch implementations
- **THEN** the maximum absolute difference between the outputs SHALL be less than 1e-4
