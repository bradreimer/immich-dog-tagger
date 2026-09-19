# Multi-Immich-Account Support

## Purpose

Today the app talks to exactly one Immich account: one `IMMICH_URL` and one `IMMICH_API_KEY`, used
for scanning, downloading, and syncing back a single library. A household running two Immich
accounts on the same server (e.g. two partners' own libraries, or a family account plus a personal
one) currently needs a separate deployment (separate `state.db`, separate identities, separate
container) per account -- even though the same dogs and cats show up in photos across both
libraries and a separate deployment can never learn from or recognize against the other's
examples.

This is a major, cross-cutting architectural change: it introduces a new scoping dimension
(*which Immich account/library does this photo belong to*) into a schema and pipeline that have
never had one, while deliberately keeping the parts of the app that reason about "which dog or cat
is this" completely unaware that dimension exists.

## User story

As an owner who manages more than one Immich account on the same Immich server, I want to
configure multiple API keys so that one instance of this app scans, classifies, and reviews photos
from all of them together -- sharing what it has learned about each dog/cat across every library --
while syncing each library's own albums/tags only from that library's own photos, never mixing one
account's photos into another account's Immich library.

## Goals

- Configure two or more Immich API keys against the same `IMMICH_URL`, each representing a
  separate Immich account/library ("account" below).
- Scan and download run per account, against that account's own Immich API key.
- Detection, embedding, classification, review, corrections, reclassification, and Insights are
  **shared** across every configured account: an `Identity` ("Rex the dog") is one identity system-
  wide, its `EmbeddingExample`s come from whichever account's photos produced them, and nearest-
  neighbor classification searches the full shared pool regardless of which account a candidate
  photo came from. Reviewing/correcting a photo from Account A can improve recognition of the same
  dog in Account B's photos, and vice versa, automatically -- no separate configuration.
- Sync writes each identity's photos back as albums/tags **separately into each account's own
  Immich library**, using only that account's own asset IDs and its own API key. Account A's Immich
  library only ever gains albums/tags/assets that came from Account A; nothing from Account B is
  ever written to it, and vice versa.
- A single configured Immich API key (today's setup) keeps working with no configuration or
  behavior change -- this is additive, not a breaking reconfiguration for existing installs.
- One account being unreachable (revoked key, network failure, permission error) does not block
  scan/download/sync for the other configured accounts -- consistent with the per-identity failure
  isolation `SyncService` already applies (issue #243/#259).
- The owner can see which account a photo, job, or sync result belongs to wherever that context
  matters (Library/Review filtering, Settings, Job Queue).

## Non-goals

- **Multiple Immich servers/URLs.** This is same-server, multiple-account only, per the request
  that prompted this spec. A different `IMMICH_URL` per account is not supported here; see Open
  Questions for whether a later iteration should relax this.
- **Cross-account deduplication of the same physical asset.** If the same photo is visible to two
  accounts (e.g. Immich partner sharing), each account tracks and syncs its own visible copy
  independently. No attempt is made to detect that two accounts' asset IDs refer to the same
  underlying photo.
- **Storing Immich API keys in `state.db`.** Keys stay environment-configured only, matching the
  existing single-account design's security posture (`GET /api/settings` already never returns
  `immich_api_key`, per issue #83).
- **Per-account identity sets, classification policy, or thresholds.** An identity is always
  global; there is no "this dog only exists in Account A" concept, and classification/review
  policy (`policy.py`) is not scoped per account.
- **Live add/remove of an account from the UI.** Like `IMMICH_URL` today, accounts are deployment
  configuration (environment variables); adding or removing one requires an edit and a restart, not
  an in-app "Add account" flow. Revisiting this as a `state.db`-managed, UI-editable concept (like
  `Identity`) is a possible future iteration, not this one.
- **Migrating or merging existing per-account Immich albums/tags.** An existing single-account
  install's data is simply attributed to one implicit account going forward (see Requirements); no
  album/tag content in Immich itself is touched by adopting this feature.

## Architecture overview

The existing system already has a clean seam for this, described in
[ADR-001](../adr/ADR-001-state-database-source-of-truth.md) and
[ADR-006](../adr/ADR-006-immich-operations-explicit-local-operations-on-demand.md): `state.db` is
the source of truth, and operations split cleanly into ones that touch Immich (`scan`, `download`,
`sync`) and ones that are local-only (`detect`, `classify`, `embed`, `learn`, `reclassify`, review,
corrections, Insights). Multi-account support rides exactly that seam:

- **Account-scoped**: everything on the Immich-touching side of that line, plus the one row that
  anchors a photo to a specific library (`Asset`). An account is a first-class row
  (`ImmichAccount`: id, name -- no key stored) so `Asset`, `SyncedAsset`, and account-scoped jobs
  can carry a stable `account_id` foreign key without ever putting a credential in `state.db`. The
  actual API key for a given account name is resolved at runtime from
  [`Config.accounts`](https://github.com/bradreimer/immich-dog-tagger/blob/main/src/immich_dog_tagger/config.py)
  (issue #348, merged) -- a `tuple[ImmichAccount(name, api_key), ...]` sourced from either the JSON
  `CONFIG_FILE` or, for a legacy install with no config file, a single synthesized account always
  named `"default"`. `Config.accounts` is never empty once any Immich credential is configured, in
  either form, so this feature's account-resolution logic never needs to special-case "legacy
  install" versus "config-file install" -- both already produce a uniform list of named accounts.
- **Globally shared, unchanged**: `Identity`, `EmbeddingExample`, `CropClassification`,
  `PetOccurrence`, review actions, Insights, Learning Progress/Metrics. None of these gain an
  `account_id` or any account-awareness at all -- `Detection`/`Crop`/`CropClassification` already
  key off `Asset`, so they inherit account scoping transitively for free without a schema change of
  their own, while the classifier's nearest-neighbor search over `EmbeddingExample` continues to
  query the whole table with no account filter, which is exactly what makes learning "share across
  accounts" require no special-casing.

This means the identity/classification/review/Insights code paths this app has spent multiple
releases hardening (DT-1003's leakage fix, DT-1004's centralized policy, ADR-003/007's
temporal/spatial weighting, ADR-004's occurrence semantics) need **no changes** for this feature.
The work is concentrated in the scan/download/sync boundary, `Asset`'s identity, and the
surfaces (CLI, jobs/schedules, Settings, Library/Review filters) that need to know an account
exists at all.

## Requirements

### FR-1: Account configuration -- done, via #348

[Issue #348](https://github.com/bradreimer/immich-dog-tagger/issues/348) (the
[JSON config file spec](json-config-file.md)) merged to `main` and already provides everything
this requirement needs:

- `Config.accounts: tuple[ImmichAccount, ...]` (`ImmichAccount` = `name` + `api_key`), populated
  from the mounted JSON `CONFIG_FILE`'s `immich.accounts` array when one is configured.
- A deployment with only the legacy `IMMICH_API_KEY` env var set (no `CONFIG_FILE`) gets exactly
  one synthesized account, named `"default"`, with no visible change anywhere in the CLI, API, or
  UI -- FR-1 is already backward compatible with zero further work.
- `Config.immich_api_key` still returns the first account's key unchanged, so every existing
  caller that hasn't been touched for multi-account support keeps working exactly as before.

**Nothing else here needs building.** The remaining requirements below (FR-2 through FR-7) are
this feature's actual scope: making the rest of the app iterate over `Config.accounts` instead of
assuming exactly one.

### FR-2: Data model

- New `ImmichAccount` table (`id`, `name` unique, `created_at`). Holds no credential -- naming a
  row is enough to join it against `Config.accounts` by `name` at runtime; the row never stores an
  `api_key` of its own.
- **Startup account sync**: on every startup, for each entry in `Config.accounts`, upsert an
  `ImmichAccount` row by exact `name` match (create it if new; an existing row is left alone
  otherwise -- names are the join key, so this needs no other identifying data). A DB row whose
  name is no longer present in `Config.accounts` (removed or renamed in configuration) is **not**
  deleted -- see Open Questions for how it should be surfaced to the owner instead. Because
  `Config.accounts` always contains a `"default"`-named account for a config-file-less legacy
  install (per FR-1), this single startup-sync step is also the entire migration path for an
  existing single-account install: no separate "is this a fresh install or an upgrade" branch is
  needed.
- `Asset` gains a required `account_id` foreign key to `ImmichAccount`. `Asset.immich_asset_id`'s
  uniqueness constraint becomes `(account_id, immich_asset_id)` rather than global, since the same
  Immich asset ID could in principle be visible under more than one account (e.g. partner sharing).
- `SyncedAsset` gains a required `account_id` foreign key, included in its existing
  `(species, identity, immich_asset_id)` uniqueness constraint.
- `PipelineJob` and `PipelineSchedule` gain a nullable `account_id`: set for account-scoped
  operations (`scan`, `download`, `sync`, `full_pipeline`), left null for local-only operations
  (`detect`, `classify`, `embed`, `learn`, `reclassify`) -- mirroring the ADR-006 split exactly.
- Backfill migration is additive and non-destructive (per this project's database-change
  conventions): every pre-existing `Asset`/`SyncedAsset` row (from before this feature existed) is
  backfilled onto the `ImmichAccount` row named `"default"` -- the same name the startup account
  sync above creates for a legacy install, so the two line up automatically with no separate
  "which account did old rows belong to" decision to make. No existing photo, classification,
  review history, or learned example is reprocessed, re-synced, or reset by this migration.

### FR-3: Scan and download

- `Scanner`/`Downloader` run once per entry in `Config.accounts`, each using that account's own
  `ImmichClient` (its own `api_key`, shared `immich_url`), and write/update `Asset` rows tagged
  with that account's `account_id`.
- Concretely, this means `api/dependencies.py`'s `get_immich_client()` (currently `@cache`-d,
  building exactly one `ImmichClient` from `config.immich_api_key`) can no longer return a single
  client -- it, and every other single-client construction site (the CLI's scan/download/sync
  commands, `AssetRepairService`, `ManualDetectionAssignmentService`, `job_execution.py`'s
  handlers), need to build or select one `ImmichClient` per account instead.
- The CLI's `scan`/`download`/`full_pipeline` commands accept an optional account selector (e.g.
  `--account <name>`); omitting it runs against every configured account in turn.
- A failure reaching one account's Immich API (bad key, network error, permission error) is
  isolated to that account: it is logged and reported, and does not prevent scan/download from
  completing for the other configured accounts in the same run.

### FR-4: Detection, embedding, classification, review -- unchanged and shared

- No behavior change to `DetectionService`, embedding generation, `IdentityClassifier`,
  `SimilarityScorer`, the review queue, corrections, reclassification, merges, clustering, or
  Insights. They already operate on `Asset`/`Crop`/`CropClassification`/`Identity`/
  `EmbeddingExample` with no notion of "library," and none of those tables' meaning changes.
- Confirming this explicitly is itself a requirement: a regression test should assert that
  classification against a shared identity draws candidates from every account's embedding
  examples, not just the account of the photo being classified.

### FR-5: Sync

- `SyncService.sync()` runs once per entry in `Config.accounts`, using that account's own
  `AlbumService`/`TagService`/`ImmichClient` (each constructed from that account's `api_key`), and
  only considers `CropClassification`s whose crop's asset belongs to that account.
- Each account's sync writes only that account's own assets into that account's own Immich albums/
  tags. An identity's photos in Account A never appear in Account B's "Dog - Rex" album, and vice
  versa, even though both albums share the same identity name.
- `SyncedAsset`'s stale-membership diffing (DT-1113) operates per account, so a correction that
  moves an Account A photo between identities only affects Account A's album/tag membership.
- The CLI's `sync` command accepts the same account selector as FR-3; omitting it syncs every
  configured account, with the same per-account failure isolation, extending the existing
  per-identity isolation pattern (`SyncSummary.failed_identities`) with a per-account dimension.

### FR-6: Jobs and schedules

- Account-scoped operations (scan, download, sync, full pipeline) carry which account they ran
  for on the `PipelineJob` row, visible in the Job Queue.
- `PipelineSchedule` supports scheduling an account-scoped operation for a specific account.
  Whether one schedule can mean "run for every configured account" or an owner must create one
  schedule per account per operation is an implementation decision -- see Open Questions.
- The existing single-running-job constraint (`has_running_job()`, ADR-006) is unchanged; an
  account-scoped job is a job like any other.

### FR-7: Settings, Library, and Review surfaces

- The Settings page lists configured accounts by name (never the key), consistent with the
  existing convention that `IMMICH_API_KEY` is write-only from the app's perspective.
- The Library and Review pages can filter by account, alongside the existing species/identity/
  reviewed-status/capture-date filters, and each item's detail panel shows which account a photo
  belongs to.
- **Everywhere a photo's own details are already shown (capture date, location), the account name
  is shown alongside them**, not only as a separate filter: the Review card, the Library detail
  panel, and the Photo Lookup page's per-detection details. This is the same "trust signal"
  treatment capture date got in
  [v1.4.0](v1.4-trustworthy-photo-library.md)/DT-1111 and location got in
  [v1.6.0](v1.6-pet-insights.md) -- account is one more fact about where a photo came from, shown
  next to the others rather than requiring a separate lookup.
- "View in Immich" / Photo Lookup links need no account-specific logic: the link resolves through
  the browser's own logged-in Immich session, not this app's server-side API key, so the existing
  `immich_link_base_url` behavior is unaffected by which account a photo came from.

## Acceptance criteria

- Given only the legacy `IMMICH_API_KEY` set (no accounts declared), the app behaves identically to
  today in the CLI, API, and UI -- no account picker, filter, or column appears anywhere.
- Given two accounts configured and both scanned, a dog corrected/reviewed only in Account A's
  photos is recognized (via the shared `EmbeddingExample` pool) in Account B's later classification
  passes, with no separate configuration needed.
- Given two accounts configured, running `sync` (no account selector) writes "Dog - Rex" (or
  whichever identity) into both accounts' Immich libraries, each containing only that account's own
  photos of Rex -- inspecting either account's Immich albums directly shows no asset ID that
  belongs to the other account.
- Given one account's API key is revoked, running `scan`/`sync` for all accounts still completes
  successfully for the other configured account(s), and the run's result names which account failed
  and why -- the same way a single bad identity's sync failure is named today rather than aborting
  the whole run.
- Given an existing single-account install upgraded to a build with this feature, all pre-existing
  `Asset`/`SyncedAsset` rows are attributed to one implicit `"default"` account -- matching the
  name `Config.accounts` already synthesizes for a config-file-less install (#348) -- and no photo
  is redownloaded, redetected, reclassified, or resynced as a side effect of the migration alone.
- Given the Library or Review page with two accounts configured, filtering by account shows only
  that account's photos, and each photo's detail panel names its account alongside its capture
  date and location.

## Open questions

- **Renaming or removing a configured account** after it already has synced data: `Config.accounts`
  resolves purely by exact string name, so renaming an account in `config.json` is
  indistinguishable from deleting the old one and adding a brand-new one with the same key --
  the old `ImmichAccount` DB row simply stops matching anything in `Config.accounts` (per FR-2's
  startup sync) and is orphaned, silently, unless the owner is told. Options: warn/flag an
  orphaned `ImmichAccount` in Settings ("configured account 'X' is no longer present in
  configuration") rather than failing silently on its next scan/sync; or support an explicit
  rename operation (like an `Identity` rename today) that re-keys the existing row instead of
  orphaning it. Needs a decision before the Settings UI for this is designed.
- **Schedule granularity**: does one `PipelineSchedule` mean "run for every configured account," or
  does an owner create one schedule per account per operation? Affects both the schema
  (`account_id` nullable-meaning-all vs. required) and the Schedules UI.
- **Two accounts, one Immich identity**: should the app do anything differently if two configured
  API keys turn out to belong to the same underlying Immich user (rather than genuinely separate
  libraries)? Current assumption is no special detection or handling is needed -- each configured
  key is trusted to represent a distinct library the owner intends to sync separately.
- **Multiple Immich servers** (different `IMMICH_URL` per account) is explicitly out of scope for
  this iteration (Non-goals), but the `ImmichAccount` model should be reviewed for whether it can
  be extended to carry its own URL later without another breaking schema change, in case that is
  ever requested. Not a concern `Config.accounts` (#348) introduces either way -- it deliberately
  has one shared `immich.url` for every account, per that spec.
- Whether this warrants a dedicated ADR once the account-renaming and schedule-granularity
  questions above are settled, alongside ADR-001/ADR-006, given how directly it extends both.
