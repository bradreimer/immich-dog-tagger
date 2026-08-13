# DT-1113: Edit previously assigned tags from the library, and fix stale Immich album membership

## **ID**

DT-1113

## **Related spec**

[v1.4-trustworthy-photo-library.md](../specs/v1.4-trustworthy-photo-library.md) (FR-3)

## **Priority**

High

## **Status**

Pending

## **Goal**

Let the owner correct any classification's identity at any time from the library (DT-1112),
including ones already reviewed weeks ago -- and make sure that correction actually fixes Immich
album membership on the next sync, not just adds a new album while leaving the photo in the old
one. The interview's stated pain point is explicit: "particularly when users notice a photo in the
wrong Immich album." Editing the tag without fixing the album would not actually solve that
problem.

## **Context**

**The tag-correction mechanism already supports this with no backend changes needed.**
`ClassificationCorrectionService.correct()` (`src/immich_dog_tagger/services/correction.py:29`)
has no guard against correcting an already-reviewed classification -- it just records another
`ReviewAction`, updates `CropClassification.identity`/`confidence`/`source`, and calls
`Learner.learn_image()`. `Learner.learn_image()`
(`src/immich_dog_tagger/services/learner.py:34`) is explicitly designed for this: its docstring
states "correcting a crop from 'Fibs' to 'Hermann' removes the stale Fibs example instead of
leaving it behind," backed by `_forget_other_identities()` (line 179). Re-correcting an
already-reviewed classification via `POST /classifications/{id}/correct` already works correctly
today -- this ticket's backend work is entirely about what happens *downstream* of that, at sync.

**The real gap is in sync/album membership.** `AlbumService.sync_identity()`
(`src/immich_dog_tagger/services/albums.py:23`) calls `self.client.add_assets_to_album(...)` --
only ever adding. `ImmichClient` (`src/immich_dog_tagger/immich.py`) has no
`remove_assets_from_album` method at all. `SyncService.sync()`
(`src/immich_dog_tagger/services/sync.py:35`) computes, per sync run, the current
`(species, identity) -> {asset_ids}` mapping from `CropClassification` state and calls
`sync_identity` once per group -- it has no concept of "this asset used to belong to a different
identity's album and needs to be removed from it." Concretely: correct a photo from "Fibs" to
"Hermann," re-sync, and the photo ends up in **both** `Dog - Fibs` and `Dog - Hermann` -- the exact
symptom the interview described.

Per [ADR-001](../adr/ADR-001-state-database-source-of-truth.md), `state.db` is the source of truth
and Immich is a presentation/export target only -- so the fix should track prior sync membership
in `state.db` and diff against it, not treat Immich's actual current album contents as
authoritative (which would mean querying Immich per sync just to find out what to undo, and would
silently "fix" any manual album edits a user made directly in Immich, which isn't this app's
place to override).

## **Implementation notes**

### Album membership fix (backend, independent of the frontend editing UI)

- Add a `SyncedAsset` model: `(species, identity, immich_asset_id)` -- the identity/species an
  asset was synced to *last time*. Populate/update it inside `SyncService.sync()` after a
  successful `sync_identity()` call.
- In `SyncService.sync()`, after computing the current `(species, identity) -> {asset_ids}`
  mapping, diff it against the previous `SyncedAsset` rows for each asset: any asset whose
  `(species, identity)` changed needs `remove_assets_from_album` called against its *old* album
  before (or after) `add_assets_to_album` is called against the new one.
- Add `ImmichClient.remove_assets_from_album(album_id, asset_ids)` to `immich.py`, mirroring
  `add_assets_to_album` (`DELETE /api/albums/{id}/assets` with the same `{"ids": [...]}` body
  shape Immich's API uses for the add endpoint -- confirm the exact verb/shape against the Immich
  API during implementation, the existing `add_assets_to_album` at immich.py:173 is the template
  to follow for error handling).
- `AlbumService` gains a `remove_from_identity(identity, asset_ids, species)` counterpart to
  `sync_identity`, used by the new removal path.
- An asset reclassified to "Unknown" (identity `None`) needs the same treatment: removed from its
  old identity album, and (per `SyncPolicy.include_unknown`, already an existing policy flag)
  either added to an "Unknown" album or left in none.

### Library editing UI (frontend + thin API reuse)

- Add an identity-correction control to each `LibraryPage` (DT-1112) result -- reuse the existing
  `correctClassification(classificationId, identity)` function in `ui/src/lib/api.ts` (already
  calls `POST /classifications/{id}/correct`; no new endpoint needed) and a component similar to
  `IdentityChooser.tsx`, scoped to that item's own species per the pattern DT-1110 established for
  the Review page.
- After a successful correction, update the item in place in the library's local state (matching
  `ReviewPage.tsx`'s existing optimistic-update pattern after `correctClassification`) rather than
  re-fetching the whole page.
- No confirmation dialog for the correction itself, consistent with
  [ux-principles.md](../specs/ux-principles.md)'s "minimal confirmation dialogs for non-destructive
  actions" -- correcting a tag is reversible (it's just another correction).

## **Acceptance criteria**

- Correcting a classification's identity from the library works identically to correcting from
  the Review page (same endpoint, same learning-example update), for both already-reviewed and
  not-yet-reviewed items.
- Re-running sync after a correction removes the asset from its previous identity's Immich album
  and adds it to the new one -- the asset never remains in a stale album after a sync following a
  correction.
- Correcting a classification to "Unknown" removes the asset from its previous identity's album,
  consistent with `SyncPolicy.include_unknown`.
- Re-running sync with no new corrections is idempotent (unchanged from today) -- this ticket adds
  removal behavior only for assets whose identity actually changed since the last sync, not a
  full album rebuild every run.

## **Testing requirements**

- `tests/test_sync.py`: extend with a test that classifies an asset to identity A, syncs (asserts
  it's added to A's album), corrects it to identity B, syncs again, and asserts it was removed
  from A's album and added to B's album -- this is the core regression test for the bug this
  ticket fixes.
- `tests/test_albums.py`: unit test for the new `remove_from_identity`/
  `remove_assets_from_album` path.
- `tests/test_e2e_review_learning_loop.py` or a new e2e test: extend the existing
  detect->classify->correct->reclassify->sync chain to include a *second*, later correction on an
  already-synced asset, asserting the final album state (not just the classification state) is
  correct.
- Frontend: manual browser verification that editing a tag from the library updates the UI
  immediately and persists on reload, plus `npm run build`/`npm run lint`.

## **Dependencies**

DT-1112 (searchable library) -- this ticket adds an editing affordance on top of the browsing
surface DT-1112 creates. The album-membership fix itself has no UI dependency and could land
first/independently if useful to de-risk it separately.

## **Suggested commit message**

`feat(DT-1113): allow re-correcting reviewed tags and fix stale Immich album membership on sync`
