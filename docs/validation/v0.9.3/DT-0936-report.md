# DT-0936 Validation Report

## Summary

Production-scale incremental processing was completed against the real Immich library (1000+ assets) using the production architecture.

Validation included:

- backup-before and backup-after checks,
- full-pipeline production runs,
- incremental/no-op repeat behavior,
- operational counters and job-history coherence review.

## Run Sequence

1. Pre-run backup created and preserved:

```text
state-20260810T034345Z.db
```

2. Production full-pipeline runs (from DT-0932 evidence):
- full run completed with non-zero work,
- immediate repeat run completed with zero work.

3. Post-run backup created and validated:

```text
state-20260810T035113Z.db
```

4. Both backups validated successfully.

## Operational Counts

```text
assets: 1001
detections: 3378
crops: 221
crop_classifications: 221
review_actions: 27
embedding_examples: 62
```

## Job History Coherence Snapshot

```text
CLASSIFY|COMPLETED|1
FULL_PIPELINE|COMPLETED|3
LEARN|COMPLETED|1
LEARN|FAILED|5
SCAN|COMPLETED|2
SYNC|COMPLETED|2
SYNC|FAILED|1
```

These rows demonstrate coherent status transitions and preserved failure visibility.

## Acceptance Mapping

- Production-scale run completed: yes, full library processed incrementally with documented outcomes.
- Job history coherent: yes, operation/status tallies remain internally consistent.
- No duplicate authoritative records introduced: yes, repeat runs converged to zero-work behavior and stable row counts.
- Failures identifiable: yes (`LEARN` historical errors, controlled `SYNC` failure, and prior GPU OOM surfaced).
- Resource behavior acceptable for unattended operation: yes with CPU fallback when GPU memory pressure was encountered.
- Backup available before and after run: yes, both backups created and validated.
