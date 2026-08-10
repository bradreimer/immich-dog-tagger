# ADR-002: Active Learning Architecture

## Status
Accepted

## Context
Classification quality improves when human corrections become reference examples.

## Decision
Human review corrections create embedding examples that feed future classification.

## Alternatives Considered
- Manual reference curation only.
- Static classifier.

## Consequences
The system improves over time but requires careful provenance tracking.
