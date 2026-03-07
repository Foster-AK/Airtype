## ADDED Requirements

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
