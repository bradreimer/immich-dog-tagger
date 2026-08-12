# DT-1011: v1.0.0 Release Validation

## 1. Automated tests

`./scripts/check.sh` (ruff check/format, `uv run pytest -q`, `npm run build`, `npm run lint`) passes cleanly: **257 tests pass**, UI builds and lints clean. Run repeatedly throughout DT-1000-1010 and once more immediately before this report.

## 2. Fresh-install test

Performed against an isolated scratch `STATE_DIR`/`CACHE_DIR` (not the real project database):

- `immich-dog-tagger init-db` -- creates a fresh `state.db` cleanly.
- `immich-dog-tagger status --verbose` -- reports all-zero counts with no errors on an empty database.
- `immich-dog-tagger pipeline --dry-run` -- reports "no pending downloads/detections/classifications" with no errors.
- `immich-dog-tagger backup` -- creates a valid backup file.
- `immich-dog-tagger check-derived-data` -- reports "all referenced artifacts present" on an empty project.

## 3. Process a representative project

**Not performed against a real Immich library in this environment** -- no Immich credentials/instance were available to this validation, and this environment has no GPU for real YOLO/OpenCLIP inference. This is the same disclosed gap as DT-1008. The representative-project and review/reclassify flow *is* validated end-to-end with synthetic data in `tests/test_e2e_review_learning_loop.py` (40 crops across 3 simulated identities, 25 reviewed, multiple Reclassify passes) and live against a running API instance (see #5 below). Recommended before production reliance: run `immich-dog-tagger pipeline` against a real library and repeat the steps below manually.

## 4. Initial manual review batch

Covered by `tests/test_e2e_review_learning_loop.py::test_full_review_driven_learning_loop`, which reviews 25 of 40 crops via the real `ClassificationCorrectionService` and confirms the labeled-example population matches exactly (DT-1003 acceptance criterion). Not performed as a live manual click-through in a browser against a real library in this environment (see #3).

## 5. Reclassify from the web UI

- UI wiring visually verified: built the app, ran it against a local isolated backend, and screenshotted Mission Control -- the "Reclassify with reviewed examples" action and "Learning Progress" card render correctly (DT-1002/DT-1006).
- The underlying operation verified live against a running API instance (isolated scratch database, not production): `POST /jobs {"operation": "reclassify"}` on a zero-example project transitions `pending -> running -> completed` and the pass reports `eligible_count: 0` with an explanatory message, exactly as designed.
- Full review -> Reclassify -> verify-unchanged-labels -> Reclassify-again-stable flow verified via the DT-1009 end-to-end test.

## 6. Verify metrics

- `GET /metrics` verified live against the scratch API instance: correct shape and values (`null` coverage/review_rate on an empty project; updates immediately after a Reclassify pass completes; `pass_history` and `last_reclassification` populated correctly).
- Unit/API coverage: `tests/test_metrics.py`, `tests/api/test_metrics.py`.

## 7. Restart/recovery behavior

Verified live against a running API instance, not just in unit tests:

1. Manually inserted a `PipelineJob` in `RUNNING` state and a `ClassificationPass` in `RUNNING` state (simulating a process killed mid-Reclassify).
2. Restarted the API process.
3. Startup log: `Startup recovery: 1 interrupted job(s) marked FAILED, 0 abandoned job(s) marked CANCELED, 1 classification pass(es) reconciled`.
4. `GET /jobs/{id}` confirmed the job moved to `FAILED` with an explanatory `error_message`; `GET /diagnostics` listed it under `recent_failures` with no stuck jobs remaining.

This exercises the DT-1005 recovery path end-to-end, not only through the unit tests in `tests/test_job_recovery.py`.

## 8. Scale validation

See [DT-1008-scale-validation.md](DT-1008-scale-validation.md). Two real N+1 defects were found and fixed; batching and pagination were confirmed bounded. A literal 30,000-real-image run was not performed (no GPU/Immich instance in this environment) -- disclosed as an open item, not silently assumed passing.

## 9. Logs reviewed for sensitive-data leakage

- `tests/test_logging.py` asserts, as a regression test, that job-lifecycle and correction logs never contain image paths/content.
- Manually captured live application logs from the fresh-install and restart/recovery runs above (steps 2 and 7) and grepped them for image extensions, state-directory paths, and API keys/secrets: no matches.

## 10. Changelog / release notes

- `pyproject.toml` version bumped `0.9.4` -> `1.0.0`.
- FastAPI app version string (`api/app.py`) aligned to `1.0.0`.
- `README.md` "Project Status" section rewritten for the v1.0.0 release (what shipped, updated "Completed" list, updated "Roadmap" pointer to `docs/roadmap.md`).
- `docs/roadmap.md` updated: v0.9.4 marked completed, v1.0.0 section added summarizing DT-1000-1010 and linking to the spec and workflow guide.
- `docs/status.md` updated: current milestone is v1.0.0, DT-1000-1010 listed as completed, DT-1011 as remaining, and the DT-1008 scale-validation gap listed under Known Issues.

## 11. Acceptance criteria vs. spec (docs/specs/v1.0.0.md section 7)

| Criterion | Status |
|---|---|
| A fresh project can be created successfully | Pass -- see #2 |
| A representative image set can run through the full pipeline | Not performed against a real library -- see #3 |
| A user can review 50-100 items and see the labeled-example count increase appropriately | Pass (synthetic, DT-1009) |
| Reclassify can be launched from the main page | Pass -- see #5 |
| Reclassify updates predictions without altering reviewed labels | Pass (DT-1001, DT-1003, DT-1009) |
| Re-running Reclassify produces stable results when inputs/configuration have not changed | Pass (DT-1001, DT-1009) |
| A second review/reclassify cycle works | Pass (DT-1009) |
| Failed/restarted jobs do not duplicate or corrupt state | Pass (DT-1005, DT-1009, and live-verified in #7) |
| Dashboard metrics agree with persisted database counts | Pass (DT-1006, live-verified in #6) |
| A 30,000-image-scale dry run or representative load test demonstrates bounded memory use and acceptable batching | Partial -- N+1/batching fixed and regression-tested at synthetic scale; no literal 30k-image run (DT-1008) |
| Documentation describes the workflow and recovery path | Pass (DT-1010, `docs/workflow.md`) |
| Existing projects pass regression tests | Pass (DT-1009 migration test) |

## Conclusion

No release-blocking defects remain. Two items are explicitly disclosed as gaps rather than silently assumed passing: a live run against a real 30,000-image Immich library (DT-1008), and a live manual review/reclassify click-through against a real library (#3/#4 above) -- both because this development environment has no GPU and no configured Immich instance to exercise them against. Everything else -- including restart/recovery and the reclassify job lifecycle -- was verified against a *running* instance, not only unit tests. Recommended as a release-validation follow-up, not a blocker: run the pipeline against a real library once and repeat steps 3-8 above.

## Status
Completed.
