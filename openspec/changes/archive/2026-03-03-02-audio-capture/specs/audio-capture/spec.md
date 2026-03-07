## ADDED Requirements

### Requirement: Audio Stream Capture

The system SHALL capture audio from the selected input device at 16000 Hz sample rate, 16-bit PCM or float32 format, mono channel, and a buffer size of 512 samples (32ms per frame).

#### Scenario: Start capture with default device

- **WHEN** `AudioCaptureService.start()` is called with device set to `"default"`
- **THEN** the system SHALL begin capturing audio from the system default input device without error

#### Scenario: Start capture with specified device

- **WHEN** `AudioCaptureService.start()` is called with a specific device index
- **THEN** the system SHALL begin capturing audio from that device

#### Scenario: Stop capture

- **WHEN** `AudioCaptureService.stop()` is called while capturing
- **THEN** the system SHALL stop the audio stream and release the device

### Requirement: Input Device Enumeration

The system SHALL enumerate all available audio input devices and return a list of device names and indices. The implementation SHALL use `sounddevice.query_devices()` (without the `kind` parameter) and filter for devices with `max_input_channels > 0`. Note: `query_devices(kind='input')` returns only a single dict for the default input device and is not suitable for listing all input devices.

#### Scenario: List devices

- **WHEN** `AudioCaptureService.list_devices()` is called
- **THEN** the system SHALL return a list of available input devices with their names and indices

#### Scenario: No input devices available

- **WHEN** no audio input devices are available on the system
- **THEN** the system SHALL return an empty list and log a warning

### Requirement: Runtime Device Switching

The system SHALL support switching the active input device at runtime without restarting the application. The switch SHALL stop the current stream and start a new stream on the selected device.

#### Scenario: Switch device during capture

- **WHEN** `AudioCaptureService.set_device(new_index)` is called while audio capture is active
- **THEN** the system SHALL stop the current stream, start a new stream on the new device, and resume capture within 200ms

### Requirement: Audio Data Ring Buffer

The system SHALL maintain a circular ring buffer of 3 seconds (48000 samples at 16kHz) using a numpy array. When the buffer is full, new audio frames SHALL overwrite the oldest data.

#### Scenario: Buffer accumulation

- **WHEN** audio frames are continuously captured for 3 seconds
- **THEN** the ring buffer SHALL contain exactly 3 seconds of the most recent audio data

#### Scenario: Buffer overflow

- **WHEN** audio capture continues beyond 3 seconds without being consumed
- **THEN** the oldest samples SHALL be overwritten by the newest samples

### Requirement: RMS Volume Calculation

The system SHALL calculate the RMS (Root Mean Square) volume for each audio frame (512 samples) and make it available to consumers for waveform visualization.

#### Scenario: RMS output during speech

- **WHEN** the user is speaking into the microphone
- **THEN** the RMS value SHALL be greater than the RMS value during silence

#### Scenario: RMS output during silence

- **WHEN** there is no audio input (silence)
- **THEN** the RMS value SHALL be close to zero

### Requirement: Thread-Safe Data Exchange

Audio frames captured in the callback thread SHALL be passed to consumer threads via a thread-safe `queue.Queue`. The callback SHALL NOT perform any blocking operations.

#### Scenario: Consumer reads audio frames

- **WHEN** a consumer calls `get_frame()` on the audio queue
- **THEN** the next available audio frame SHALL be received in FIFO order
