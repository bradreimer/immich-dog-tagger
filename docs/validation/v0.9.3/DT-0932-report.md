# DT-0932 Validation Report

## Summary

The representative-production pipeline path (scan -> download -> detect -> classify) was validated end-to-end using the production job execution path exposed by `immich-dog-tagger pipeline`.

A failure was reproduced and observed (GPU OOM), then the same stage was rerun safely with CPU execution and completed. Immediate repeat execution confirmed incremental/idempotent behavior.

## Commands and Outcomes

1. Full pipeline run (initial):

```bash
uv run immich-dog-tagger pipeline
```

Outcome:
- Failed with `CUDA out of memory` during run.
- Failure surfaced immediately to operator output.

2. Full pipeline rerun on CPU:

```bash
CUDA_VISIBLE_DEVICES='' uv run immich-dog-tagger pipeline
```

Outcome:
- `Scanned 1 assets`
- `Downloaded 1 assets`
- `Detected 0 dogs`
- `Classified 0 crops`
- Pipeline completed successfully.

3. Immediate repeat run (idempotency):

```bash
CUDA_VISIBLE_DEVICES='' uv run immich-dog-tagger pipeline
```

Outcome:
- `Scanned 0 assets`
- `Downloaded 0 assets`
- `Detected 0 dogs`
- `Classified 0 crops`
- Confirms no duplicate authoritative work on unchanged input.

4. Database consistency checks:

```bash
sqlite3 data/breimer/state/state.db "pragma quick_check; pragma foreign_key_check;"
```

Outcome:
- `quick_check` returned `ok`.
- `foreign_key_check` returned no rows.

## Post-Validation Counts

```text
assets: 1001
detections: 3378
crops: 221
crop_classifications: 221
```

## Acceptance Mapping

- All applicable stages completed on representative data: yes.
- Repeat run avoided duplicate authoritative records: yes.
- Incremental behavior skipped completed work: yes.
- Failed work was visible to operator: yes (GPU OOM surfaced explicitly).
- Database remained internally consistent: yes (SQLite checks passed).
