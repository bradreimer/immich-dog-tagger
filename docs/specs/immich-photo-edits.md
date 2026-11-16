# Immich Photo Edits

## Purpose

Immich lets people rotate, crop and mirror a photo after upload. The edit is non-destructive: the
uploaded file stays unchanged, and Immich renders the edit on request. immich-dog-tagger
downloaded only the unedited original, so after an edit the crops, detection boxes and Photo
Lookup image kept the old orientation and framing, even after Repair.

## User story

As a reviewer, I want Repair to use the rotation and crop I applied to a photo in Immich, so that
detections, crops and the photo shown in Review match the photo as I edited it.

## Goals

- Every photo download from Immich asks for the edited rendition, so detection, crops, Photo
  Lookup and manual assignment all use the photo as edited.
- Repair on a photo edited after it was first processed re-runs the pipeline on the edited photo.
- Photos without edits, and Immich servers without photo editing, behave as before.

## Non-goals

- Detecting edits during scheduled scans and re-running the pipeline automatically. Edits after
  the first download take effect when the person selects Repair.
- Writing edits back to Immich.
- Keeping review history through Repair (Repair still replaces that photo's detections).

## Requirements

- `ImmichClient.download_asset()` calls `GET /api/assets/{id}/original?edited=true`. Immich
  returns the edited rendition when the photo has edits, and the original otherwise.
- If Immich responds `400` to the request with `edited`, the client retries once without it.
- The edited rendition is already upright and carries no orientation tag, so `open_upright()`
  uses its pixels as-is, even though the asset's cached exif dimensions describe the original.
- No new Immich API key permission is needed: the endpoint still requires `asset.download`.

## Acceptance criteria

- Given a photo rotated 90° in Immich, when the person selects Repair, then new crops are upright
  and detection boxes align with the rotated photo in Review and Photo Lookup.
- Given a photo cropped in Immich, when the person selects Repair, then detection runs on the
  cropped image only.
- Given a photo with no edits, when the person selects Repair, then behavior is unchanged.
- Given an Immich server that rejects `edited`, when the person selects Repair, then Repair
  succeeds using the original.
- A repaired, edited photo is not flagged by stale-detection auto-repair: Repair sets
  `upright_detected_at`, which excludes the photo from that check.

## Open questions

- Should a scan notice newly edited photos (for example, from an Immich edit timestamp) and
  offer Repair automatically? Deferred to a follow-up.
