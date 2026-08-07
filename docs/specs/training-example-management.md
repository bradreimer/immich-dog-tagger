# Training Example Management

## Purpose
Improve the quality and maintainability of training examples used by the learning system.

## User Story
As an operator, I want training examples to be curated and traceable so that feedback improves classification quality over time.

## Goals
- Define a clear lifecycle for training examples.
- Preserve provenance and quality metadata.
- Make pruning and replacement safe and repeatable.

## Non-goals
- Full retraining orchestration.
- Changes to external model architectures.

## Requirements
- Store example quality signals and source context.
- Distinguish confirmed-positive, confirmed-negative, and uncertain examples.
- Support deterministic pruning or replacement policies.
- Expose example management outcomes through status/reporting paths.

## Acceptance Criteria
- Example lifecycle operations are documented and test-covered.
- Low-value examples can be pruned without manual database edits.
- Operators can inspect provenance and quality state for examples.

## Open Questions
- Should pruning be policy-based only, or allow manual overrides?
