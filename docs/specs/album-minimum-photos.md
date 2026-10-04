# Album Minimum Photos

Tracking issue: [#405](https://github.com/bradreimer/immich-dog-tagger/issues/405).

## Purpose

Sync creates an Immich album and an Immich tag for every identity. Owners who want to label every
pet they recognize end up with an album for each one, so they have avoided labeling acquaintances
at all (for example, filing them under "Not a Dog or Cat"). Tags are cheap to browse and search;
albums are only worth having for pets that appear often.

## User story

As the owner, I want to tag every pet I recognize, with those tags synced to Immich, but only get
an album for pets with at least 50 photos.

## Goals

- Every synced identity is tagged in Immich, regardless of how many photos it has.
- An album is created only when the identity has at least `ALBUM_MIN_PHOTOS` photos (default 50).
- Crossing the threshold on a later sync creates the album and adds all of that identity's photos.

## Non-goals

- A Settings UI control for the threshold. It is an environment variable for now.
- Deleting or emptying an existing album when an identity falls below the threshold. The app never
  removes an album the owner may be using.
- Changing tag behavior.

## Requirements

- The photo count is the number of distinct assets synced for a `(species, identity)` after the
  existing confidence policy, including manual tags.
- Below the threshold, `SyncService.sync()` skips `AlbumService.sync_identity` but still calls
  `TagService.sync_identity`.
- Stale-membership removal is unchanged for both albums and tags. Removal from an album that does
  not exist is already a no-op.
- `ALBUM_MIN_PHOTOS` defaults to `50`. `0` restores the old behavior (an album for every identity).
  A negative or non-integer value is a startup error.

## Acceptance criteria

- An identity with fewer photos than the threshold is tagged and gets no album.
- An identity at the threshold gets both.
- An identity that crosses the threshold gets the album, with all its photos, on the next sync.
- Corrections still remove stale album and tag membership.
- `ALBUM_MIN_PHOTOS` is documented in `.env.example` and `docs/deployment.md`.

## Open questions

None.
