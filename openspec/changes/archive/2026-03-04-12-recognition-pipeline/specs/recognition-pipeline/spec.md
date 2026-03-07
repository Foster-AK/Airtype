## ADDED Requirements

### Requirement: Batch Recognition Pipeline

The system SHALL implement a batch recognition pipeline that accumulates audio during a speech segment, submits the complete audio buffer to the ASR engine when speech ends, and forwards the result to text injection.

#### Scenario: Complete Batch Flow

- **WHEN** VAD transitions to SPEECH_ENDED after 3 seconds of speech
- **THEN** the accumulated audio SHALL be submitted to ASR, and the recognized text SHALL be injected into the target application

### Requirement: Streaming Recognition Pipeline

The system SHALL implement a streaming recognition pipeline that continuously feeds audio chunks into the ASR engine, produces partial results, and injects the final result upon completion.

#### Scenario: Streaming Partial Results

- **WHEN** the user speaks for 5 seconds with streaming mode enabled
- **THEN** partial text results SHALL be produced during speech, and the final result SHALL be injected after speech ends

### Requirement: Pipeline as Composable Class

`RecognitionPipeline` SHALL accept injected dependencies (AudioCapture, VadEngine, ASREngine, TextInjector) to allow testing with mock components.

#### Scenario: Pipeline with Mock Components

- **WHEN** a pipeline is created with mock AudioCapture, VadEngine, and ASREngine
- **THEN** the pipeline SHALL operate correctly using the mock components
