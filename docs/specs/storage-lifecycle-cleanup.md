# Storage Lifecycle Cleanup

## Purpose
Stop the pipeline from retaining local disk copies of source photo bytes once they're no longer
needed, so `cache_dir` doesn't grow unboundedly across a full library run.

## User Story
As a self-hoster running the pipeline against a large Immich library, I want `download` and
`detect` to avoid keeping files on disk that nothing downstream uses, so that disk usage stays
proportional to what the app actually needs rather than to the size of my whole photo library.

## Context
`download` fetches the full-resolution original for every scanned asset into `cache_dir`,
regardless of file type. `detect` only processes image types it can decode (jpg/jpeg/png/heic,
per `is_supported_image`); video and RAW assets (`.mov`, `.mp4`, `.cr2`, ...) are downloaded in
full but silently skipped forever, wasting the download and the disk space with no path to ever
being used.

For supported images, once `detect` has generated crops, nothing downstream touches the
original again: `embed`/`classify` operate on crop paths, and `sync` operates on Immich asset IDs
via the API. The original is only needed to run detection itself. `DerivedDataService.check()`
already only expects an original to exist for `AssetStatus.DOWNLOADED` assets, not
`DETECTED`/later ones -- so the existing health-check contract already assumes originals aren't
required past that point.

Immich remains the authoritative store for the photo bytes themselves (per
[ADR-001](../adr/ADR-001-state-database-source-of-truth.md)); the local cache is a disposable
working copy, not the source of truth, so removing it is recoverable via `download --force`.

## Goals
- Never download an asset type that `detect` can never process.
- Delete a supported image's cached original once `detect` has successfully produced its crops.

## Non-goals
- Retroactively re-scanning or migrating already-downloaded files from before this change (a
  `download --force` pass naturally cleans up stale unsupported-type downloads as a side effect,
  but no dedicated migration/cleanup command is in scope).
- Changing what `is_supported_image` accepts (still jpg/jpeg/png/heic only).
- Automatically re-downloading a missing original when `detect --force` is run against it.

## Requirements
- `download` marks an asset whose extension isn't a supported image type with a new terminal
  status (`AssetStatus.UNSUPPORTED`) instead of downloading it, and removes any already-cached
  file for it (covers a `download --force` pass over pre-existing unsupported downloads).
- `detect`, after successfully generating crops for an asset (`crop_writer` configured), deletes
  that asset's cached original. Deletion failure is logged, not fatal to the job.
- `detect` run without a `crop_writer` configured leaves originals untouched, since no crop
  exists to stand in for them.

## Acceptance Criteria
- An asset with an unsupported extension is never downloaded; its status becomes `UNSUPPORTED`.
- A `download --force` pass over an already-downloaded unsupported-type asset removes its cached
  file and flips it to `UNSUPPORTED`.
- After `detect` completes for a supported image with a `crop_writer`, the asset's cached
  original no longer exists on disk, while its crop(s) do.
- `detect` without a `crop_writer` does not delete originals.
- `DerivedDataService.check()` continues to pass for assets whose originals were cleaned up this
  way (no false-positive "missing download" reports).

## Open Questions
- None -- `detect --force` on an asset whose original was already cleaned up requires a
  `download --force` first to fetch it again; this is accepted as the expected operational
  trade-off rather than solved automatically here.
