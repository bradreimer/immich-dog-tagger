# DT-1118: Scan silently caps at 1000 assets because Immich pagination is never followed

## **ID**

DT-1118

## **Related spec**

None -- bug fix, not new behavior.

## **Priority**

High

## **Status**

Completed

## **Goal**

Fix a production-blocking bug: running `scan` (directly or via `pipeline`) against an Immich
library with more than 1000 assets only ever discovers the first 1000, with no error or warning.
A full scan of a library must discover every asset, not just the first page.

## **Context**

`ImmichClient.list_assets()` (`immich.py`) called Immich's `POST /api/search/metadata` exactly
once with `{"size": 1000}` and returned `data["assets"]["items"]` directly. That endpoint is
paginated -- the response also carries `assets.nextPage`, a cursor that must be echoed back as
`page` in a follow-up request to get the next batch. `list_assets()` never read or followed
`nextPage`, so any library with more than 1000 assets silently lost everything past the first
page. `Scanner.scan()` (`scanner.py`) already diffs `list_assets()`'s result against `state.db` by
`immich_asset_id` and only inserts/updates what's missing, so it's naturally idempotent and safe
to call repeatedly -- the bug was entirely in the client only ever seeing page one.

This wasn't caught earlier because dev/test libraries stayed under 1000 assets; it surfaced when
preparing for production against a real, larger library.

## **Implementation notes**

- `immich.py`: `list_assets()` now loops, sending `page` (Immich's `nextPage` cursor value from
  the previous response, `None`/omitted on the first request) and accumulating `items` from every
  page, stopping when a response's `nextPage` is falsy. Behavior for single-page libraries
  (`nextPage` absent or `null`) is unchanged.
- No changes needed in `scanner.py`, `cli.py`, or the job runner -- they already treat
  `list_assets()` as returning the full asset list and `Scanner.scan()` was already
  insert-or-skip, so subsequent incremental scans (new files added to Immich later) work the same
  way they did before, just now correctly seeded by a first scan that actually saw everything.

## **Acceptance criteria**

- `list_assets()` returns every asset in the library, not just the first 1000, for libraries with
  multiple pages.
- A single-page library (no `nextPage` in the response) behaves exactly as before.
- `scan` against a library with >1000 assets records all of them in `state.db`, not just the first
  1000.

## **Testing requirements**

- `tests/test_immich.py::test_list_assets_follows_pagination` -- mocks a two-page response
  (`nextPage: "2"` then `nextPage: None`), asserts both pages' assets are returned and that the
  second request's body echoes `page: "2"`.
- Existing `test_list_assets` (single page, no `nextPage` key) continues to pass unchanged.
- Full `./scripts/check.sh` passes.

## **Dependencies**

None.

## **Suggested commit message**

`fix(DT-1118): follow Immich pagination in list_assets so scan sees the whole library`
