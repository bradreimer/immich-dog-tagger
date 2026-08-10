# Review Workflow

## Purpose
Allow humans to validate and correct uncertain classifications.

## User Story
A user wants to quickly review detected dogs and assign identities.

## Goals
- Fast correction workflow
- Keyboard-friendly operation
- Track completed actions

## Non-goals
- Full photo editor
- Cloud workflow

## Requirements
- Show pending classifications
- Allow correction
- Allow skip
- Persist actions

## Behavioral Rules
Correct actions create learning examples.
Skipped items remain historically visible.

## Data Model Impact
Uses CropClassification, ReviewAction, EmbeddingExample.

## API Impact
Review and correction endpoints.

## Acceptance Criteria
Users can process a queue without manually editing database state.

## Open Questions
How should confirmed corrections update the reference set?
