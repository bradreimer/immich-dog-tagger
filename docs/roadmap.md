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

## v1.6.0 - Pet Insights

See [docs/specs/v1.6-pet-insights.md](specs/v1.6-pet-insights.md) and
[ADR-004](adr/ADR-004-pet-occurrence-observations.md).

Goal:
A read-only "fun layer" on top of confirmed pet identifications, combining existing
`Identity`/`CropClassification` data with metadata Immich already computes per photo (capture
time, GPS/location, recognized people) -- without turning the project into a general-purpose
photo analytics tool, and without storing conclusions ("favorite human," "favorite place") as
data. Tracking issue: [#94](https://github.com/bradreimer/immich-dog-tagger/issues/94).

Completed:
- #94: new `PetOccurrence` fact table, materialized as a side effect of AUTO
  classification/review correction/reclassification settling an identity for a crop; `Asset`
  gained cached location/people/favorite fields sourced from the same Immich response the
  scanner already fetches; `InsightsService` computes summary/timeline/places/people at read
  time; read-only `GET /api/dogs/{id}/insights/*` endpoints; a per-dog Insights page in the UI;
  `immich-dog-tagger backfill-occurrences` for existing libraries.

Explicitly not planned this iteration (see spec Non-goals): Best Friends (pet-to-pet
co-occurrence), On This Day, a Pet World Tour map, Milestones, any personality inference, AI
slideshows, writing conclusions back to Immich, or a precomputed insights cache.

Exit criteria:
Completed.

## v1.7.0 - Pluginable Insight Providers

See [docs/specs/v1.7-pluginable-insights.md](specs/v1.7-pluginable-insights.md) and
[ADR-005](adr/ADR-005-insight-provider-plugin-architecture.md). Tracking issue:
[#110](https://github.com/bradreimer/immich-dog-tagger/issues/110).

Goal:
Turn the mechanism that determines a v1.6.0-style fun insight (favourite human, favourite place,
and future ones like a Milestones "1000th confirmed photo") into a pluggable unit — one
self-contained provider per insight, registered explicitly -- so v1.6.0's deferred Milestones, On
This Day, and Best Friends can each land as an independent addition instead of growing
`InsightsService`'s core methods and API surface one bespoke endpoint at a time.

Completed:
- #110: `InsightProvider` protocol + explicit `INSIGHT_PROVIDERS` registry
  (`services/insights/providers.py`; no dynamic/third-party plugin loading -- this stays an
  in-codebase extensibility mechanism); `services/insights.py` split into a package
  (`aggregations.py`, `providers.py`, `service.py`) with the favourite-place/favourite-human/
  Immich-favorite-count logic previously inline in `InsightsService.summary()` reorganized onto
  shared aggregation helpers the providers also use, as a behavior-preserving refactor --
  `InsightsService.summary()`'s method signature and response shape are unchanged; new read-only
  `GET /api/dogs/{id}/insights/cards` endpoint and a `DogInsightsPage` card grid that render
  whatever's registered, so future providers need no endpoint or frontend change; a first new
  provider landed under this architecture as proof -- `TotalPhotosMilestoneProvider`, a
  round-number confirmed-photo-count Milestone (e.g. "1000th confirmed photo").

Explicitly not planned this iteration (see spec Non-goals): On This Day, Best Friends, Pet World
Tour map, per-provider enable/disable settings, any dynamic/third-party plugin loading.

Exit criteria:
Completed.

## v1.8.0 - Library as an Approval Workspace

See [docs/specs/v1.8-library-approval-workspace.md](specs/v1.8-library-approval-workspace.md)
and [docs/competitive-analysis-library-workflow.md](competitive-analysis-library-workflow.md).
Tracking issue: [#139](https://github.com/bradreimer/immich-dog-tagger/issues/139).

Goal:
Turn the flat, photo-first Library into an identity-first approval workspace -- select a species,
select a dog or cat, then approve clusters of recommendations for that pet -- so labeling cost
scales with the number of pets rather than the number of photos. Clustering runs over the
`CropClassification.embedding` values that already exist, and a cluster approval is N ordinary
corrections through `ClassificationCorrectionService`, not a new kind of state.

Completed:
- #140 (FR-1): species -> pet selection as the Library's primary axis, held in a
  `LibraryWorkspaceProvider` context the later stories read from; the flat "all photos" view, its
  review-status and capture-date filters, and pagination are unchanged.
- #141 (FR-2/FR-3): agglomerative clustering over cosine distance, computed on demand as a
  request-scoped read that writes nothing, and one-action approval of an explicitly submitted
  member list routed through the existing correction service.
- #142 (FR-4): per-photo selection within a cluster -- members start selected, the approve control
  names the count it will apply to, and the approval submits an explicit id list the server
  validates against the pet's own candidate pool rather than re-deriving membership. The generic
  `useSelection` hook it introduces is the app's first multi-select primitive.
- #143 (FR-5): sort the cluster list and each cluster's members by capture date or confidence
  (default confidence descending -- approve the surest group first), from the data already
  eager-loaded for review/library items, with a classification-id tiebreak and null capture dates
  sorting last under both date directions.
- #144 (FR-6): reject a recommendation as "not this pet" -- the negative signal the workflow never
  had -- stored in its own table so every count deriving from a `ReviewAction` keeps meaning what
  it meant, and suppressed in `IdentityClassifier.classify()` so a rejection survives Reclassify.
- #146 (FR-8): detection coverage reported alongside automation rate, so the Metrics tab can see
  photos detection never found instead of only scoring the crops it did make.
- #147 (FR-11): tag a photo whose pet the detector missed, as a light fact about the asset that
  sync reads and the classifier ignores -- it never becomes a reference example, and it survives a
  `--force` reprocess that would destroy anything hung off the detection chain.
- #148 (FR-10): merge a duplicate or misspelled identity into another -- classifications,
  reference examples and pet occurrences move to the target, review history is left intact, the
  source stays as a deactivated tombstone, and the merge is recorded in `identity_merges`.
- #149 (FR-9): owner-facing tagging sensitivity, mapped to a threshold in `policy.py` alone and
  traceable through `classifier_version`, plus a debounced auto-Reclassify after a settled review
  batch, queued through the job system so self-started work is as visible as owner-started work.

Explicitly not planned (see spec Non-goals): cold-start clustering for a pet with no examples
(FR-7 dropped, [#145](https://github.com/bradreimer/immich-dog-tagger/issues/145) closed as not
planned -- the Review tab already serves that case); approvals triggering an Immich sync, per
[ADR-006](adr/ADR-006-immich-operations-explicit-local-operations-on-demand.md); removing or
changing the review queue; changing classification policy/thresholds/the embedding model; changing
`GET /api/library`'s query semantics; or a fully automatic label-without-the-owner model.

Exit criteria:
Completed.

---

## v1.9.0 - Automatic Spatial Classification

See [docs/specs/v1.9-automatic-spatial-classification.md](specs/v1.9-automatic-spatial-classification.md)
and [ADR-007](adr/ADR-007-automatic-spatial-proximity-classification.md). Tracking issue:
[#181](https://github.com/bradreimer/immich-dog-tagger/issues/181).

Goal:
Extend v1.5.0's continuous, fail-open weighting approach from capture-date proximity to location
proximity, so two visually similar dogs/cats photographed in different characteristic places are
disambiguated by where a photo was taken, the same way v1.5.0 already disambiguates by when.

Completed:
- #181: `EmbeddingExample` gained a denormalized `latitude`/`longitude` snapshot (mirroring
  `captured_at`); `SimilarityScorer` now also computes a `spatial_weight` (Gaussian decay over
  haversine distance, ~2km scale, fail-open when a coordinate is missing on either side);
  `IdentityClassifier` ranks/selects candidates by
  `similarity * temporal_weight * spatial_weight` while continuing to report each winning match's
  raw, unweighted cosine similarity as confidence; a new `location-mismatch` review/library reason
  is checked alongside `temporal-mismatch` (temporal takes precedence when both fire).

Explicitly not planned (see spec Non-goals): an owner-facing setting to tune the decay curve;
reverse-geocoded/place-name-based comparison (the cached `country`/`state`/`city` fields stay
Insights-only); retroactive recomputation of existing classifications outside the normal
Reclassify flow.

Exit criteria:
Completed.

---

## v1.12.0 - Immich Tag Sync

See [docs/specs/immich-tag-sync.md](specs/immich-tag-sync.md). Tracking issue:
[#230](https://github.com/bradreimer/immich-dog-tagger/issues/230).

Goal:
Sync wrote each classified identity back to Immich as an album only. Also write it as an Immich
**tag**, so identity is a first-class, searchable attribute of the asset itself in Immich, not
just implied by album membership.

Completed:
- #230: new `TagService` (structurally identical to `AlbumService`) and `ImmichClient.list_tags`/
  `create_tag`/`tag_assets`/`untag_assets`, wrapping Immich's `/api/tags` endpoints. `SyncService`
  gained an optional `tags: TagService | None` constructor parameter; when provided, `sync()` tags
  every asset it adds to an identity's album and untags stale membership the same way it already
  removes stale album membership (DT-1113). Both production sync call sites (`cli.py`'s dry-run
  path, `services/job_execution.py`'s `_sync_handler`) always pass a `TagService`, so tag sync is
  on by default, not opt-in. Deliberately out of scope: writing to Immich's People/face-recognition
  surface (a materially bigger integration, see `docs/competitive-analysis-library-workflow.md` G8).

Exit criteria:
Completed.

---

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
