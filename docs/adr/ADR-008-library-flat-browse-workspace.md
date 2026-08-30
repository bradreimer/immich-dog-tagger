# ADR-008: Library reverts to a flat browse-and-correct workspace

## Status

Accepted.

## Context

v1.8.0 ([ADR context in docs/specs/v1.8-library-approval-workspace.md](../specs/v1.8-library-approval-workspace.md))
made the Library identity-first: pick a species, pick a pet, approve clusters of that pet's pending
recommendations. This scaled labeling cost with pets instead of photos, which was the right fix for
the problem it targeted -- confirming a backlog of pending recommendations for a known pet.

It came at a cost the original analysis didn't weigh: an owner auditing or spot-checking the
catalogue by a *different* axis -- "everything unreviewed from last month", "find this one photo
and fix it", "everything low-confidence" -- now has to first commit to a pet before seeing anything,
even though the flat, multi-filter, sortable, paginated view (species + identity + reviewed +
date-range, sort by date or confidence, 50 at a time) is the natural shape for that kind of task and
is what the Library was before v1.8.0.

## Decision

The Library's primary (and now only) page is the flat, filterable, sortable, paginated catalogue
with a per-photo details panel, as specified in
[v1.11-library-browse-and-correct.md](../specs/v1.11-library-browse-and-correct.md). Concretely:

- `LibraryPage` drops the species/pet selection step (`LibraryWorkspaceProvider`, `PetSelector`)
  and the cluster panels (`ClusterPanel`, `ConfirmedClusterPanel`, `ClusterCard`) as its UI. Every
  filter (species, pet, reviewed, date range) is independent and optional.
- Per-photo correction moves off the grid card entirely (no more inline "Correct to..." dropdown on
  each thumbnail) and onto the Review page, reached via a details-panel "Edit" link that opens
  `/review?classification_id={id}`. The Review page is extended to load and correct one arbitrary
  classification by id, not only step through the active queue.
- The cluster-approval **backend** -- `RecommendationClusterService`, `ConfirmedClusterService`,
  `ClusterApprovalService`, the `/library/clusters*` routes, and their tests -- is not removed. It
  becomes unreachable from the Library page's default view, not deleted: nothing in this decision
  claims bulk cluster approval was the wrong feature, only that it should not be the thing an owner
  sees first when opening the Library. Whether and how to re-expose it (a separate page, a second
  tab) is left open in the spec's "Open questions" rather than decided here, since deleting a
  tested, working subsystem on a UI-routing decision is a separate, larger call this ADR does not
  need to make.

## Alternatives considered

- **Keep the pet selector, add the flat filters as a second mode/tab.** Rejected: it keeps two
  entry points doing overlapping jobs (both ultimately call the same `GET /api/library`), and the
  Library's problem statement -- "look at classified pets, then correct mistakes" -- doesn't need a
  mode switch to answer. One page, one mental model.
- **Merge the two: show cluster panels above the flat grid when a pet is selected.** Rejected for
  the same reason as above, and because it keeps the "must pick a pet to do anything" gate for the
  panels even if the grid below no longer has it -- half a fix.
- **Delete the cluster/approval backend entirely** since the UI no longer calls it. Rejected here:
  that is a real feature (bulk approve/reject/reassign, with its own clustering algorithm,
  accounting, and test suite) that nothing in this decision says was a mistake to have built --
  only that it shouldn't gate the Library's primary view. Removing working, tested capability is a
  bigger and harder-to-reverse call than a page-layout decision should make on its own; left as an
  explicit open question in the spec instead.

## Consequences

- Bulk-approving many photos for one pet in one action -- v1.8.0's core throughput win -- has no UI
  path today. An owner with a large pending backlog for one pet is back to correcting one photo at
  a time via Review/Library, exactly as before v1.8.0. This is accepted as the cost of this
  decision, not an oversight; re-exposing the existing backend is comparatively cheap if it turns
  out to be missed.
- `useSelection` (the generic multi-select hook v1.8.0's FR-4 built "outside the Library feature...
  since the flat library grid is the next caller") gets no new caller from this change, since the
  flat grid here is single-select (one photo, one details panel). It is left in place, unused by
  the Library, since it is a small, generic, already-tested primitive and not itself part of what
  this ADR removes.
- Two Library-adjacent specs now describe different UIs for `/library`: v1.8.0 (superseded UI,
  requirements FR-6/FR-8/FR-9/FR-10 still current on their own surfaces) and v1.11.0 (current UI).
  Both stay as historical record; v1.8.0 is annotated to point forward rather than rewritten.
