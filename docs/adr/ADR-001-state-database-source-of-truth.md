# ADR-001: State Database as Source of Truth

## Status
Accepted

## Context
Immich is an external photo management system. Using it as the primary state store would make learning history and review state difficult to manage.

## Decision
Maintain a local database containing assets, detections, classifications, review actions, and learning examples.

## Alternatives Considered
- Store all metadata in Immich.
- Maintain only filesystem state.

## Consequences
The system owns its own history and can evolve independently from Immich.
