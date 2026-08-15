# Roadmap

## v0.4.0 - Human Review Foundation

Goal:
Create a reliable human review workflow.

Completed:
- Review API
- Review queue
- Browser UI
- Correct action
- Skip action
- Review history tracking

Exit criteria:
Completed.

---

## v0.5.0 - Review Workflow Stabilization

Goal:
Make human review and active learning observable and dependable.

Features:
- Learning statistics
- Review progress visibility
- Review workflow improvements
- Better embedding example management
- Documentation of workflow

Exit criteria:
- Review actions are measurable
- Learning progress is visible
- Workflow documented

---

## v0.9.4 - Dynamic Dog Management

Goal:
Remove hard-coded dog names and let operators manage dog identities from Mission Control.

Completed:
- persistent dog identity model
- dog management API
- Mission Control dog management UI
- regression coverage for empty-install behavior

Exit criteria:
Completed.

---

## v1.0.0 - Review-Driven Learning Loop

See [docs/specs/v1.0.0.md](specs/v1.0.0.md) for the full specification and [docs/workflow.md](workflow.md) for the operator-facing workflow guide.

Goal:
Let a user with a new project and no labeled examples progressively reduce manual review through a review -> reclassify loop, without needing to understand embeddings or model internals.

Completed:
- Centralized nearest-neighbor classifier policy (DT-1004)
- Reclassification service/job that reuses stored embeddings and reviewed examples without touching reviewed ground truth (DT-1001)
- Review-to-example ground-truth hardening, closing a real leakage defect (DT-1003)
- Job lifecycle/idempotency/recovery for Reclassify (DT-1005)
- Reclassify action on Mission Control and a Learning Progress dashboard (DT-1002, DT-1006; the dashboard moved to its own Metrics tab in v1.1's DT-1103)
- Pipeline/correction lifecycle logging (DT-1007)
- Scale validation: two N+1 defects found and fixed (DT-1008)
- End-to-end review-driven learning loop regression tests (DT-1009)
- v1.0 user and operator documentation (DT-1010)

- DT-1011 release validation against the full v1.0.0 acceptance criteria (docs/validation/v1.0.0/DT-1011-release-validation.md)

Exit criteria:
Completed.

---

## v1.1.0 - Automation Coverage Dashboard

See [docs/specs/v1.1-automation-coverage-dashboard.md](specs/v1.1-automation-coverage-dashboard.md).

Goal:
Answer "is the system getting better at doing the work I used to have to do manually?" with a dedicated Metrics tab, complete per-pass trend data, and one prominent automation-rate number.

Completed:
- DT-1103: dedicated Metrics tab, next to Mission Control
- DT-1101: snapshot labeled-example count and review-queue size per classification pass
- DT-1102: reconcile the review-queue metric definition and add a prominent automation-rate metric

Exit criteria:
Completed.

---

## v1.2.0 - Visual Style Refresh

See [docs/specs/v1.2-visual-style-refresh.md](specs/v1.2-visual-style-refresh.md).

Goal:
Give the app one consistent visual identity -- a sidebar navigation shell, a single blue action
accent, consistent status colors, and a stat-tile/chart pattern -- across all four existing tabs,
replacing the horizontal pill nav and per-page ad-hoc styling.

Completed:
- DT-1104: blue accent design tokens, validated status/categorical color palette, sidebar
  navigation shell, reusable stat-tile primitive
- DT-1105: rolled the style out to Mission Control, Metrics (including new donut and trend
  charts built from existing `GET /metrics` data), Job Queue, and Review's surrounding chrome
- DT-1106: UX review follow-ups -- destructive-button contrast fix, relative "last updated" time,
  Mission Control next-action banner, Metrics automation trend delta
- DT-1107: moved dog management to its own `/dogs` page and sidebar tab
- DT-1108: consolidated Metrics' trend section into one dual-axis Progress Over Time chart

Exit criteria:
Completed.

---

## v1.3.0 - Cat Support

See [DT-1110: Add cat support alongside dogs](https://github.com/bradreimer/immich-dog-tagger/issues/66).

Goal:
Extend detection, classification, review, and sync to cats alongside dogs, sharing one review
queue and one correction UI -- no separate tab, page, or mode for cats. Species is hardcoded to
`dog`/`cat`, not a general-purpose config.

Completed:
- DT-1110: species-scoped identities and crops (additive migration, backward compatible with
  existing dog-only projects), species-scoped nearest-neighbor classification, unified review
  queue with a per-item species-scoped identity chooser, species-aware Immich album naming, and a
  per-species Learning Progress breakdown

Exit criteria:
Completed.

## v1.4.0 - Trustworthy Photo Library

See [docs/specs/v1.4-trustworthy-photo-library.md](specs/v1.4-trustworthy-photo-library.md).

Goal:
Shift the product's primary mental model from "process a review queue" to "build and maintain a
trustworthy, searchable library of tagged photos," surfaced by a mock user interview. Show photo
capture date as a first-class trust signal, let corrections happen any time (not just once, from
a queue that empties out), and use capture date as an additional classification signal to catch
temporally impossible matches between visually similar individuals.

Completed:
- DT-1111: show photo capture date prominently during review
- DT-1112: searchable, paginated library of every classified photo (reviewed and unreviewed),
  filterable by identity/species/reviewed-status/capture-date range
- DT-1113: edit any previously assigned tag from the library, and fix a real gap found while
  scoping this work -- re-syncing after a correction never removed the asset from its stale
  identity's Immich album, only added it to the new one
- DT-1114: flag (not silently accept) a classification whose photo date falls outside a
  candidate identity's known active date range, via an optional owner-set active range per
  identity (Dogs & Cats page) and a new `date-conflict` review/library reason (**superseded by
  v1.5.0**, below)

Explicitly not planned (see spec Non-goals): review queue removal, undo/redo for classification
actions.

Exit criteria:
Completed.

## v1.5.0 - Automatic Temporal Classification

See [docs/specs/v1.5-automatic-temporal-classification.md](specs/v1.5-automatic-temporal-classification.md)
and [ADR-003](adr/ADR-003-automatic-temporal-recency-classification.md).

Goal:
Replace DT-1114's manually maintained per-identity active date range with automatic, continuous
recency weighting derived entirely from existing photo evidence -- so an aging pet's changing
appearance, a pet passing away, and a new visually similar pet arriving are all handled without
the owner configuring anything.

Completed:
- #91: removed `Identity.active_from`/`active_until` (schema, migration, API, Dogs & Cats page
  UI) entirely; `SimilarityScorer` now weights each candidate example by how closely its own
  capture date aligns with the photo being classified, and `IdentityClassifier` ranks/selects
  using that weighted score while continuing to report each winning match's raw, unweighted
  cosine similarity as confidence; the `date-conflict` review/library reason is now
  `temporal-mismatch`.

Explicitly not planned (see spec Non-goals): date-of-birth/date-of-death inference, an
owner-facing setting to tune the decay curve, retroactive recomputation of existing
classifications outside the normal Reclassify flow.

Exit criteria:
Completed.

## Active Learning Improvements

Goal:
Increase classification quality through better feedback loops.

Potential areas:
- improved reference-example selection
- reference-set curation workflows
- confidence analysis

## Productization

Goal:
Make the tool easier to operate.

Potential areas:
- polished CLI
- complete web workflow
- automated synchronization
