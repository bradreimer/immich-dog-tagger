# Friends in Frame: Pet Co-occurrence Network on the Metrics Tab

## Purpose

Nothing in the app shows how pets relate to each other across the library. Per-identity Insights
([v1.6-pet-insights.md](v1.6-pet-insights.md)) explicitly deferred "Best Friends" (pet-to-pet
co-occurrence). This spec adds a library-wide visualization to the Metrics tab: which animals tend
to appear together in the same photos.

This is a visualization of **photo co-occurrence**, not animal behavior, and the UI must not imply
otherwise.

## User story

As an owner, I want to see my dogs and cats as photo thumbnails connected by how often they appear
in the same photos, so I can see at a glance who is usually photographed together.

## Goals

- A "Friends in Frame" card on the Metrics tab: subtitle "Which animals tend to appear together in
  your photos?"
- A network of every active pet as a node, drawn as its own **key thumbnail** (not a colored dot),
  with its name. Edges encode co-occurrence count by thickness and opacity.
- Stay readable from 1 to 50+ pets: show all nodes, only the strongest edges by default.
- A "Most Common Pairs" row beneath the network, ranked by co-occurrence count.
- A key thumbnail per pet: the clearest, most circle-friendly crop available.
- Co-occurrence counts are read-time derived from `PetOccurrence` (ADR-004): no new tables, no
  stored conclusions.

## Non-goals

- No new graph/visualization dependency (SVG + a small deterministic layout module).
- No legend, no per-edge numbers by default, no giant statistics.
- No claim of friendship or behavior; no statistic that the data model cannot already back.
- No new face/pose model. "Front-facing" is not detectable from stored data (see Key thumbnail).
- No change to review, classification, or sync behavior.

## Requirements

### Key thumbnail (backend)

`FriendsInFrameService.key_crop_ids()` picks one crop per identity from its `PetOccurrence` rows:

1. Only crops that are not flagged `not_animal` and whose `Crop.species` matches the identity.
2. Human-confirmed occurrences (`REVIEW`/`MANUAL`) rank ahead of `AUTO`, so a classifier mistake is
   never promoted to a pet's face.
3. Within a tier, score = `Detection.confidence` (the clarity signal from
   [top-photos-by-clarity.md](top-photos-by-clarity.md)) x squareness (`min(w,h)/max(w,h)`, so the
   box fits a circle without cropping the animal) x size factor (`min(1, min(w,h)/256)`, so a
   sharp tiny crop does not beat a large one).
4. Ties break on the lowest crop id. Deterministic, explainable, no pixel analysis at request time.

The detector does not record head pose, so the pick is "clearest, most circular crop", a proxy for
"clearest front-facing". An identity with no eligible crop has no key thumbnail; the UI falls back
to an initial.

### Co-occurrence API

`GET /api/metrics/friends-in-frame` returns:

- `nodes`: every active identity: `id`, `name`, `species`, `image_count` (distinct photos with a
  confirmed occurrence), `key_crop_id` (nullable).
- `edges`: every identity pair sharing at least one photo: `a_id`, `b_id` (`a_id < b_id`), `count`
  (distinct shared photos). Cross-species pairs (a dog and a cat) count.

### Visibility strategy (UI, pure functions)

- Default **Strong** view: each pet's strongest K relationships (K = 3 up to 8 pets, 2 up to 20,
  1 beyond), union deduplicated, with very weak edges (below 8% of the strongest) suppressed.
- **Top 25**: the 25 strongest edges overall. **All**: every edge.
- "Minimum appearances together" slider applies on top of any mode; shown only when the data has
  a range worth filtering.
- A "Show more connections" control and a "Showing X of Y" note; connections disappear before
  thumbnails ever do.
- Label density: with more than 12 pets, only the most connected pets and the hovered/focused
  neighborhood show names by default; the rest reveal on hover.

### Layout

- Deterministic force-directed layout (seeded from identity ids): strong edges pull closer, weak
  ones sit farther, high weighted-degree pets drift to the center, pets with no co-occurrence sit on
  the perimeter. Collision-aware so thumbnails never overlap.
- The layout depends on the data and canvas size only, never on hover, focus, mode or slider, so
  positions are stable across interactions and sessions.
- Responsive: node diameter 48-64px on wide screens (scaled by `image_count`), 40-52px on narrow
  screens, and the canvas gets taller as the pet count grows.

### Interaction

- **Hover a pet**: enlarge, highlight its edges, dim everything else, show counts on its edges.
- **Click a pet**: focus mode. The pet moves to the center, its relationships fan out by strength,
  the rest recede to the perimeter. A clear "Back to all friends" control and the Escape key
  return to the overall network.
- **Hover an edge**: tooltip "Fibs + Henri / 42 images together" plus "18% of Fibs' photos" for
  each side, computed from `image_count` (existing data).
- Counts are also shown on the three strongest edges at rest.
- Hovering a pair card highlights its edge in the network.

### Most Common Pairs

Compact horizontal cards (thumbnail ↔ thumbnail, "A + B", "N images together"), ranked by
co-occurrence count. Top 6 shown initially in a horizontally scrolling row; "Show more" expands to
at most 24.

Clicking (or pressing Enter on) a pair card opens the Library at
`/library?identity=A&identity=B`: an **AND** query showing the crops of both pets from photos that
contain both ([#401](https://github.com/bradreimer/immich-dog-tagger/issues/401)). `GET /library`
treats a repeated `identity` param as AND, matched against `PetOccurrence` so the results agree
with the pair's count. There is no manual multi-pet control: the Library shows the extra pet as a
removable "Photos also with" chip, and "Review these" is hidden while it is active (Review has no
AND filter).

### States

- No pets: friendly empty message.
- One pet: the pet, centered, with "No relationships yet".
- Two pets: both thumbnails side by side with their edge (or "No shared appearances yet").
- No co-occurrences: thumbnails with no edges and "No shared appearances yet".
- Large library: automatically uses the simplified Strong view.

## Acceptance criteria

- The Metrics tab shows "Friends in Frame" with the real data and no legend.
- Counts match distinct shared photos; key thumbnails follow the ranking above.
- Layout is identical across re-renders for the same data and canvas size.
- Fixtures with 1, 2, 5, 20 and 50 pets keep every thumbnail visible and the edge count bounded in
  the default view.
- `uv run pytest`, `uv run ruff check`, and the UI `build`/`lint`/`test` all pass.

## Open questions

- Should a future detector-side head-pose or sharpness signal replace the squareness/size proxy
  for the key thumbnail? Not now: it needs a new model or per-image pixel analysis.
- Should deactivated pets optionally appear? Excluded for now; they are retired identities.
