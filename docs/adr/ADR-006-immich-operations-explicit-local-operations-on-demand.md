# ADR-006: Immich operations are explicit; local operations may run on demand

## Status
Accepted

## Context

The app's operations divide cleanly along a line that had never been written down: some reach out
to Immich over the network, and some only touch data already inside the container.

- **Touch Immich**: `scan` (lists assets), `download` (fetches originals), `sync` (creates albums
  and changes album membership). `full_pipeline` includes scan and download, so it is in this group
  too.
- **Local only**: `detect`, `embed`, `classify`, `reclassify`, `learn` — plus, under
  [v1.8](../specs/v1.8-library-approval-workspace.md), recommendation clustering and cluster
  approval.

The distinction started mattering when v1.8 scoping raised two independent questions with the same
shape: should approving a cluster of 200 photos trigger a sync so the albums update immediately
([#141](https://github.com/bradreimer/immich-dog-tagger/issues/141)), and should finishing a review
batch trigger a Reclassify so the owner sees the effect of their corrections without clicking
anything ([#149](https://github.com/bradreimer/immich-dog-tagger/issues/149))?

Answering those case by case would have produced an inconsistent triggering model, one convenience
feature at a time — which is how an app ends up quietly doing network work its operator did not ask
for.

## Decision

**Anything that touches Immich runs only when the operator asks for it, or on a schedule they
configured.** No feature may trigger a scan, download, or sync as a side effect of some other
action. An approval, a correction, a review batch, or any future bulk edit settles state in
`state.db` and stops there; Immich converges on the next explicit or scheduled sync.

**Local-only operations may be triggered automatically**, including as a side effect of the
owner's work, because they cost nothing outside the container and cannot surprise Immich.

**Long-running work runs as a job and appears in the job queue**, whether it was started by hand,
by a schedule, or automatically, so the owner can see and monitor everything substantial the app is
doing.

That last rule has a boundary, forced by the job system's design: `PipelineJobRunner._run()`
permits exactly one running job at a time (`has_running_job()`), by deliberate design
([#50](https://github.com/bradreimer/immich-dog-tagger/issues/50)). So:

- **Interactive, bounded writes stay synchronous** and are not jobs — a cluster approval, a single
  correction, creating a dog. Routing these through the queue would make them fail or block behind
  a running pipeline, which is unacceptable for something the owner just clicked.
- **Request-scoped reads stay reads** — recommendation clustering, the review queue, metrics. A
  read is not an operation, and the API already serves non-trivial ones without a job. If
  clustering later proves slow enough to feel like an operation, promoting it to a job with cached
  assignments is the remedy, decided by measurement rather than up front.
- **Everything else that runs for a while is a job**: every pipeline stage, Reclassify, sync.

A mixed operation inherits the stricter rule: `full_pipeline` scans and downloads, so it is an
Immich operation and stays explicit or scheduled.

## Alternatives considered

- **Decide per feature.** What was happening implicitly. Each decision looks reasonable alone
  ("surely the album should update after I approve 200 photos"), and the accumulated result is an
  app that reaches out to Immich at times its operator cannot predict.
- **Make everything explicit, including local work.** Consistent and simple to explain, but it
  charges the owner a click for work that costs nothing and has no external effect — and it would
  have killed the auto-Reclassify in #149, whose entire value is that the owner sees their review
  work pay off without knowing to press a button.
- **Make everything automatic, including sync.** Matches what Apple Photos and Immich's own face
  recognition do. Rejected: those tools own their whole stack, while we are a guest in someone
  else's photo library, and this project's operator controls are a deliberate differentiator rather
  than debt.
- **Put every operation in the job queue, without exception.** The literal reading of the
  monitoring preference. Rejected because of the single-active-job constraint above: it would make
  an interactive approval fail whenever a pipeline was running.

## Consequences

- Approving a cluster ([#141](https://github.com/bradreimer/immich-dog-tagger/issues/141)) writes
  identity to `state.db` and nothing else. Albums converge on the next sync the owner runs. This
  removed the sync-enqueue and debounce work that issue was otherwise going to carry.
- Auto-Reclassify after a review batch
  ([#149](https://github.com/bradreimer/immich-dog-tagger/issues/149)) is permitted — Reclassify is
  local, idempotent, and never mutates a reviewed label — and must run through the job system so it
  is visible in the queue like any other operation.
- Recommendation clustering can be computed on demand inside a request without being a job, which
  keeps [v1.8](../specs/v1.8-library-approval-workspace.md)'s first cut small.
- Future features get their answer from this ADR instead of relitigating it: a feature that wants
  Immich to change must ask the owner, and a feature that only rearranges local state does not have
  to.
- The rule is worth stating in reverse as a review check: if a code path can reach `ImmichClient`
  or `AlbumService` without an operator action or a schedule behind it, that is a defect against
  this ADR.
