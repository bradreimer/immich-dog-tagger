# Immich Tag Sync

Tracking issue: [#230](https://github.com/bradreimer/immich-dog-tagger/issues/230).

## Purpose

Sync currently writes each classified identity back to Immich as an **album** only
(`AlbumService`, e.g. `Dog - Fibs`). Albums are a browsing collection; they don't attach identity
as an attribute of the asset itself, so there's no way to see or search "which pet is in this
photo" from Immich's own asset view, search, or timeline. This adds a second, additive sync
target: Immich's native **Tags** (`/api/tags`), so a synced photo carries its identity as a
first-class, searchable label directly on the asset.

## User Story

As an owner reviewing photos in Immich (not this app), I want each photo of a specific dog or cat
tagged with that pet's name, so I can find and filter photos by pet directly in Immich without
depending on browsing this app's albums.

## Goals

- Every asset `SyncService.sync()` places in an identity's album also gets tagged with that
  identity in Immich.
- Correcting a photo away from an identity removes the stale tag, the same way it already removes
  stale album membership (issue #113 / DT-1113).
- Tag naming mirrors album naming exactly (`{Species} - {Identity}`, e.g. `Dog - Fibs`) so the two
  surfaces stay predictable and in lock-step.

## Non-goals

- Writing to Immich's People / face-recognition surface. That is a materially bigger integration
  (writing into a namespace Immich's own ML owns, reconciling against face-recognition state) and
  is called out as its own future decision in `docs/competitive-analysis-library-workflow.md` (G8)
  and `docs/status.md`. Tags are a purely additive use of an API Immich already exposes for
  external labeling.
- Replacing or removing album sync. This is additive.
- A settings toggle to disable tag sync. Not requested; can be added later if it turns out to be
  needed (e.g. an owner who doesn't want Immich's tag list populated).
- Hierarchical/nested tags (parent tag per species with identity as a child tag). Flat naming
  matches the existing album convention and needs no extra parent-tag bookkeeping.

## Requirements

- `ImmichClient` gains `list_tags`, `create_tag`, `tag_assets`, `untag_assets`, wrapping Immich's
  `GET /api/tags`, `POST /api/tags`, `PUT /api/tags/{id}/assets`, and `DELETE /api/tags/{id}/assets`
  respectively (mirroring the existing album methods' shape and error handling).
- A new `TagService`, structurally identical to `AlbumService`: `ensure_tag`/`sync_identity` finds
  or creates the identity's tag and tags the given assets; `remove_from_identity` untags assets and
  is a no-op (never creates a tag) when the tag doesn't exist yet, matching
  `AlbumService.remove_from_identity`'s existing DT-1113 contract.
- `SyncService` gains an optional `tags: TagService | None` constructor parameter. When provided,
  `sync()` calls the tag service alongside the album service for both new membership and stale-
  membership removal, over the exact same `(species, identity) -> asset_ids` map already computed
  for albums (manual tags from issue #147/#200's `ManualAssetTag` included, since they already feed
  that same map). `dry_run` skips tag writes exactly as it already skips album writes.
- Production sync call sites (`cli.py`'s dry-run path, `services/job_execution.py`'s `_sync_handler`)
  construct and pass a `TagService` so tag sync is always on, not opt-in.

## Acceptance Criteria

- A `sync()` run tags every asset in an identity's album with that identity's Immich tag.
- A correction that moves a photo to a different identity (or to Unknown) removes the stale tag on
  the next sync, mirroring the existing stale-album-membership behavior.
- `sync(dry_run=True)` performs no Immich writes (album or tag).
- Existing album-only behavior and tests are unaffected — `SyncService` without a `tags` argument
  behaves exactly as before.
- Covered by unit tests for `ImmichClient`'s new methods, `TagService`, and `SyncService`'s tag
  wiring.

## Open Questions

None.
