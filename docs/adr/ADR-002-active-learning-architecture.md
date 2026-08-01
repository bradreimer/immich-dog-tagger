# ADR-002: Active Learning Architecture

## Status
Accepted

## Context
Classification quality improves when human corrections become training data.

## Decision
Human review corrections create embedding examples that feed future classification.

## Alternatives Considered
- Manual retraining only.
- Static classifier.

## Consequences
The system improves over time but requires careful provenance tracking.
