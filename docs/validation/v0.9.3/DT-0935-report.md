# DT-0935 Validation Report

## Summary

Immich synchronization safety was validated with dry-run preview, controlled real sync, repeat sync, and explicit failure-path visibility checks.

## Commands and Outcomes

1. Dry-run preview:

```bash
uv run immich-dog-tagger sync --dry-run
```

Outcome:

```text
Would sync:
Hermann: 46
Henri: 27
Fibs: 26
Cooper: 2
Unknown: 3
```

2. Controlled real sync:

```bash
uv run immich-dog-tagger sync
```

Outcome:

```text
Hermann: 46
Henri: 27
Fibs: 26
Cooper: 2
Unknown: 3
```

3. Repeat dry-run (idempotency check):

```bash
uv run immich-dog-tagger sync --dry-run
```

Outcome:
- Planned sync set remained stable with no unexpected identity drift.

4. Failure-path validation (invalid API key):

```bash
IMMICH_API_KEY=invalid uv run immich-dog-tagger sync
```

Outcome:
- Sync failed safely with visible error: `Immich API error 401: {"message":"Invalid API key"}`.
- Failure persisted in job history.

## Job History Evidence

```text
10|SYNC|COMPLETED
14|SYNC|FAILED|Immich API error 401: {"message":"Invalid API key"}
15|SYNC|COMPLETED
```

## Acceptance Mapping

- Expected albums created/updated: validated through successful sync completion and identity counts.
- Expected assets targeted for organization: yes (identity-level asset counts reported in dry-run and run).
- Repeat sync idempotent behavior: validated via stable repeat dry-run plan.
- No unintended removal behavior exercised by tool design: sync path is additive/assignment-based; no delete operation was triggered.
- Sync failures visible: yes (explicit operator error and failed job record).
- `state.db` remained authoritative: sync plans and job outcomes derived from `state.db` and persisted in job history.
