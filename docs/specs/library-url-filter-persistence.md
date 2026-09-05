# Library URL Filter Persistence

## Purpose

Keep the Library page's filters, sort, and pagination reflected in the browser URL, so a
refresh (or a copied/bookmarked link) returns to the same filtered view instead of resetting
to defaults.

## User story

As a user reviewing the Library, I want the page's filters to be reflected in the URL, so that
if I refresh the page I'm still looking at the same dogs.

## Goals

- Reflect the Library page's current filters (species, pet identity, review status, captured
  date range), sort order, and pagination offset in the URL query string.
- Restore that state from the URL on initial load, including a hard refresh.
- Keep the URL minimal: omit query params that are at their default value.

## Non-goals

- Browser back/forward navigation between individual filter changes (URL updates use
  `history.replaceState`, not `pushState`, so filter tweaks don't spam browser history).
- Persisting the selected thumbnail/detail-panel state in the URL.
- Any other page besides Library (this is the only page with these filters today; "Photo
  Library" is not a separate tab).

## Requirements

- FR-1: On mount, `LibraryPage` reads `species`, `identity`, `reviewed`, `capturedAfter`,
  `capturedBefore`, `sort`, and `offset` from `window.location.search`, falling back to
  existing defaults for any missing/invalid value.
- FR-2: Whenever any of those values change, the page updates the URL query string via
  `history.replaceState`, omitting params equal to their default.
- FR-3: Restoring `offset` from the URL must not be immediately reset to `0` by the existing
  "filters changed -> reset pagination" effect on initial mount.

## Acceptance criteria

- Given the Library page with non-default filters applied, when the page is refreshed, then
  the same filters, sort, and page are shown.
- Given a Library URL with query params for a subset of filters, when the page loads, then
  only those filters are applied and the rest use defaults.
- Given filters at their default values, the URL has no query string.

## Open questions

None.
