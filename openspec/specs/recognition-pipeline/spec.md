# Recognition Pipeline Spec

## Purpose

This capability defines how Airtype coordinates audio capture, voice activity detection, ASR inference, and text injection into two pipeline modes: batch and streaming. It also defines the composability contract that allows the pipeline to operate with injected dependencies for testability.

---

## Requirements

### Requirement: Batch Recognition Pipeline

The system SHALL implement a batch recognition pipeline that accumulates audio during a speech segment, submits the complete audio buffer to the ASR engine when speech ends, and forwards the result to text injection.

#### Scenario: Complete Batch Flow

- **WHEN** VAD transitions to SPEECH_ENDED after 3 seconds of speech
- **THEN** the accumulated audio SHALL be submitted to ASR, and the recognized text SHALL be injected into the target application

---
### Requirement: Streaming Recognition Pipeline

The system SHALL implement a streaming recognition pipeline that continuously feeds audio chunks into the ASR engine, produces partial results, and injects the final result upon completion.

#### Scenario: Streaming Partial Results

- **WHEN** the user speaks for 5 seconds with streaming mode enabled
- **THEN** partial text results SHALL be produced during speech, and the final result SHALL be injected after speech ends

---
### Requirement: Pipeline as Composable Class

`RecognitionPipeline` SHALL accept injected dependencies (AudioCapture, VadEngine, ASREngine, TextInjector) to allow testing with mock components.

#### Scenario: Pipeline with Mock Components

- **WHEN** a pipeline is created with mock AudioCapture, VadEngine, and ASREngine
- **THEN** the pipeline SHALL operate correctly using the mock components

---
### Requirement: Flush and Recognize on Manual Stop

BatchRecognitionPipeline SHALL provide a flush_and_recognize() method that forces ASR processing of any accumulated audio buffer. This method SHALL stop audio accumulation, stop VAD consumption, extract the buffered audio, and submit it to the ASR engine on the background executor thread.

#### Scenario: Flush with Accumulated Audio

- **WHEN** flush_and_recognize() is called while audio has been accumulated during a speech segment
- **THEN** VAD consumption SHALL be stopped
- **THEN** the accumulated audio SHALL be submitted to the ASR engine for recognition
- **THEN** the recognition callback SHALL be invoked with the result

#### Scenario: Flush with No Accumulated Audio

- **WHEN** flush_and_recognize() is called but no audio has been accumulated
- **THEN** VAD consumption SHALL be stopped
- **THEN** the recognition callback SHALL be invoked with an empty string
- **THEN** no ASR processing SHALL occur
