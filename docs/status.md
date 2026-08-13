# Current Status

## Completed
- Detection pipeline
- Classification pipeline
- Review queue API
- React review interface
- Correction workflow
- Skip workflow
- Review action tracking
- API hardening and review service-boundary cleanup
- Learning and review statistics
- DT-0901 through DT-0944 (job system, scheduling, backup/recovery, production validation, dynamic dog management -- v0.9.0 through v0.9.4)
- DT-1000 v1.0.0 architecture audit
- DT-1004 centralized nearest-neighbor classifier policy
- DT-1001 reclassification service/job
- DT-1003 review-to-example ground-truth hardening (fixed a real leakage defect)
- DT-1005 job lifecycle/idempotency/recovery for Reclassify
- DT-1002 + DT-1006 Reclassify action and Learning Progress dashboard
- DT-1007 pipeline/correction lifecycle logging
- DT-1008 scale validation (fixed two N+1 defects; documented gap: no literal 30k-image run performed in this environment)
- DT-1009 end-to-end review-driven learning loop test suite
- DT-1010 v1.0 user and operator documentation (docs/workflow.md)
- DT-1011 v1.0.0 release validation (see docs/validation/v1.0.0/DT-1011-release-validation.md)
- DT-1103 dedicated Metrics tab, next to Mission Control
- DT-1101 per-pass labeled-example-count/review-queue-size snapshots
- DT-1102 reconciled review-queue metric and prominent automation-rate metric
- DT-1104 visual style foundations: blue accent tokens, validated status/categorical palette,
  sidebar navigation shell, stat-tile primitive
- DT-1105 rolled the visual style out to all four pages, including Metrics' donut and trend
  charts
- DT-1106 UX review follow-ups: destructive-button contrast fix, relative "last updated" time,
  Mission Control next-action banner, Metrics automation trend delta
- DT-1107 moved dog management to its own `/dogs` page and sidebar tab
- DT-1108 consolidated Metrics' trend section into one dual-axis Progress Over Time chart
- DT-1109 fixed a 500 on `POST /classifications/{id}/correct` (raw ORM object with a binary
  embedding column was reaching FastAPI's JSON encoder)
- DT-1110 cat support alongside dogs: species-scoped identities and crops, species-scoped
  nearest-neighbor classification, unified dog+cat review queue with per-item species-scoped
  identity chooser, species-aware Immich album naming (also fixed a same-name-cross-species
  album-collision bug in `SyncService.sync()`), per-species Learning Progress breakdown, and a
  backward-compatible additive migration for existing dog-only projects
- DT-1111 show each photo's own capture date next to its prediction/confidence everywhere a
  classification is shown (Review page and the review export text), plumbed through
  Crop -> Detection -> Asset with no N+1 query regression
- DT-1112 searchable, paginated Library page (new `/library` route and sidebar tab) showing every
  classified photo, reviewed and unreviewed alike, filterable by identity/species/reviewed-status/
  capture-date range -- the existing `/review` queue is unchanged
- DT-1113 identity correction control on each Library entry (reuses the existing
  `POST /classifications/{id}/correct` endpoint), plus the real fix underneath it: a new
  `SyncedAsset` table tracks each asset's last-synced `(species, identity)` membership so
  `SyncService.sync()` can detect and remove stale Immich album membership after a correction --
  previously an asset corrected from one identity to another stayed in both albums forever, since
  `sync_identity()` only ever added
- DT-1115 fixed a production bug: `review_queue_stats().remaining` (behind the Mission Control
  banner and sidebar "Review" badge) counted every unreviewed classification including
  confidently-classified ones, so it could claim "N images need review" while the actual `/review`
  queue was empty -- it now reuses `review_queue_count()`, the same definition `/metrics` already
  used, so `remaining` matches what `/review` actually returns everywhere it's surfaced
- DT-1114 date-aware classification: `IdentityClassifier.classify()` takes the crop's own capture
  date and flags (never silently excludes) a candidate whose match falls outside that identity's
  optional owner-set active date range (`Identity.active_from`/`active_until`, editable from the
  Dogs & Cats page via a new `set_active_range`/`PUT /dogs/{id}/active-range`), surfaced as a new
  `date-conflict` review/library reason; fails open with zero behavior change for crops with no
  capture date or identities with no range set
- DT-1116 fixed [GitHub issue #12](https://github.com/bradreimer/immich-dog-tagger/issues/12):
  "Clear list" in Job Queue > History only cleared frontend state, so a refresh brought every job
  straight back -- `PipelineJob` gained a `visible` flag, `POST /jobs/clear-history` hides
  (never deletes) finished jobs server-side, and `GET /jobs` excludes them by default; pending/
  running jobs are never hidden

## Current Milestone
v1.4.0 Trustworthy Photo Library -- released (DT-1111 through DT-1114). See
[docs/specs/v1.4-trustworthy-photo-library.md](specs/v1.4-trustworthy-photo-library.md).

## Next Work
No queued numbered milestone. Candidates: improved reference-example selection, reference-set
curation workflows, and confidence analysis (see docs/roadmap.md "Active Learning Improvements"),
or the spec's own open questions (library as default landing page, hard-excluding vs. flagging a
date conflict once there's real usage data, auto-suggesting an identity's active range from its
reviewed examples' capture dates).

## Workflow Notes
- New features should begin with a spec in docs/specs/.
- Implementation-sized work should be captured in docs/tickets/.
- Documentation should be updated alongside code changes.

## Known Issues
- Some pipeline status counters may need future cleanup.
- Detection/classification status ownership needs review.
- Endpoint-level API auth is not implemented yet.
- DT-1008's scale validation used synthetic-scale regression tests rather than a literal 30,000-real-image run (no GPU/Immich instance in the development environment); a real-library run is recommended before relying on it at that scale in production.
