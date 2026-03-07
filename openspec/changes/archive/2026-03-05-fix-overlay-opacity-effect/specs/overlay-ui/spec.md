## MODIFIED Requirements

### Requirement: Slide Animation

The capsule SHALL animate in when appearing (slide up + fade in, 200ms) and SHALL animate out when disappearing (slide down + fade out, 150ms). The fade animation SHALL use a temporary QGraphicsOpacityEffect that is attached only during the animation and removed immediately after the animation completes. The capsule SHALL NOT retain any QGraphicsEffect during its normal visible state.

#### Scenario: Capsule Appear Animation

- **WHEN** voice input is activated
- **THEN** the capsule SHALL slide in from below with a 200ms animation

#### Scenario: No Graphics Effect After Show Animation

- **WHEN** the show animation completes
- **THEN** the capsule SHALL have no QGraphicsEffect attached
- **THEN** the capsule SHALL render directly without offscreen buffering

#### Scenario: Capsule Background Preserved After Device Switch

- **WHEN** the user switches the audio input device via the capsule DeviceSelector dropdown
- **THEN** the capsule rounded-rectangle background SHALL remain visually unchanged
