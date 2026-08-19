# Competitive analysis: our library workflow vs. faces workflows

**Author:** product analysis, 2026-08-19
**Scope:** Immich Dog Tagger's library/review workflow compared with the *faces* (people
recognition) workflows in Adobe Lightroom Classic, Immich, and Apple Photos — plus
`immich-pet-tagger`, the only direct pet-identity competitor found.
**Status:** research input. Nothing here is committed work; the recommendations are candidates
for specs in [docs/specs/](specs/) and GitHub Issues.

---

## 1. Bottom line

We are not competing on detection or classification quality — we are competing on **the loop a
person runs to get from "a pile of photos" to "a library I trust."** Measured that way:

- **We are the only tool in the set that treats a human correction as durable, explainable ground
  truth.** Apple and Immich clusters are opaque, rebuildable artifacts; Lightroom's names are
  keywords. Our `state.db` provenance, per-match explanation, and idempotent Reclassify are real,
  defensible differentiation that no competitor offers at any price.
- **We lose badly on the first hour.** Every competitor delivers visible value at *zero* labels
  via unsupervised clustering. We deliver nothing until the owner has hand-reviewed 50–100 crops
  ([docs/workflow.md §2](workflow.md)). That is the single widest gap in this analysis, and it is
  closable with data we already have on disk.
- **We lose on confirmation throughput.** Our maximum rate is one photo per interaction,
  everywhere. Lightroom names an entire stack in one keystroke; Immich assigns a multi-select of
  unassigned faces in one action. This is a linear-vs-constant difference in how long it takes to
  tag a library.
- **Our primary noun is the photo; every competitor's is the person.** Library, Review, and
  Metrics are all photo-centric grids. "Show me Fibs, tell me what still needs my attention about
  Fibs, let me fix Fibs" has no home — Insights is per-dog but deliberately read-only.

The strategic read: our differentiation is in *trust* (evidence, provenance, correctness over
time), and the competition's is in *speed to first value*. We should keep investing in trust and
close exactly enough of the speed gap to stop losing owners in the first session.

---

## 2. Method and confidence

- **Our side** was read directly from this repository at commit time: `LibraryPage.tsx`,
  `LibraryEntryCard.tsx`, `ReviewPage`/`ReviewActions`/`KeyboardHints`, `services/review_query.py`,
  `services/dogs.py`, `services/sync.py`, `policy.py`, [docs/workflow.md](workflow.md),
  [docs/specs/v1.4-trustworthy-photo-library.md](specs/v1.4-trustworthy-photo-library.md), and
  [docs/status.md](status.md). Claims about what we do and don't have are verified in code, not
  from memory.
- **Competitors** were verified against vendor documentation and current public sources in August
  2026 (see §10). Two vendor doc pages (Apple Support, Adobe Helpx) were unreachable from this
  environment's egress proxy, so those specifics come from search excerpts *of those same vendor
  pages* rather than a direct read. The affordances cited are longstanding and cross-confirmed by
  multiple sources; treat exact UI wording, not the capability, as the soft part.
- **Not evaluated:** Google Photos (does group pet faces, but was outside the requested set),
  PhotoPrism, Synology Photos, digiKam.

---

## 3. The competitive set at a glance

| | **Dog Tagger** | **Lightroom Classic** | **Immich** | **Apple Photos** | **immich-pet-tagger** |
|---|---|---|---|---|---|
| Subject | Dogs + cats | Humans only | Humans only | Humans **and pets** | Pets |
| Runs locally | Yes | Yes | Yes | Yes (on-device) | Yes |
| Value at zero labels | **None** | Unnamed face stacks | Unnamed person clusters | Named-ready clusters | None (enrollment first) |
| Bootstrap action | Review 50–100 crops one at a time | Type a name on a stack | Name a cluster | Name a suggestion | Upload reference photos |
| Bulk confirm | **No** | Yes (whole stack) | Yes (multi-select faces) | Yes-ish (Confirm Additional Photos) | Yes (review queue) |
| Merge identities | **No** | Effectively, via renaming | Yes | Yes | n/a |
| Negative signal ("not X") | **No** | Reject suggestion | Detach / unassign face | "X is Not in This Photo" | "Not a pet" |
| Rescue a missed subject | **No** | Draw Face Region | Assign unassigned face | No | No |
| Explains *why* it matched | **Yes** (example, similarity, date) | No | No | No | Partly (confidence) |
| Human correction is durable ground truth | **Yes (ADR-001)** | Keywords in metadata | Cluster state | Opaque | Reference set |
| Date used as a matching signal | **Yes (v1.5)** | No | No (birthday is display only) | No | No |
| Owner-tunable thresholds | No (fixed 0.80) | No | Yes (admin settings) | No | Yes |
| Where results are searchable | Immich **albums** | Keywords / People view | Native People + search | Native People & Pets | Immich **person tags** |

---

## 4. How the competitors' faces workflows actually work

### Lightroom Classic — "name the stack"
Face indexing runs on demand when the user enters People view. Detected faces are **stacked by
similarity under "Unnamed People"**; typing a name under a stack tags every photo in it at once.
Once a few names exist, Lightroom proposes matches with a **checkmark to confirm** and an X to
reject. Undetected faces can be added manually with **Draw Face Region**. `Library > Find Faces
Again` re-scans with options to skip already-indexed photos or manually confirmed faces. Names
become **keywords** — portable, exportable metadata, not app-private state.
**Pets are not supported.** Detection occasionally surfaces animals as false positives, and
community reports say cat/dog detection present in LR6 was removed in later versions.

*What it does better than us:* stack-level naming (constant-time labeling), manual region rescue,
and metadata portability.

### Immich — "cluster first, correct later"
Faces are detected on preview images, embedded, and clustered with a **DBSCAN-derived algorithm**
using core points (a face needs a minimum number of similar neighbors to seed a person; non-core
faces can join but not create). Clusters appear with no user input; naming a cluster names all of
it. The person page supports **merge**, **hide**, **favorite/pin**, **set date of birth** (age
display), and **change the cover photo**. Unassigned faces can be **assigned in bulk**, and a face
can be **detached** back to unassigned through edit-faces mode. Recognition of leftover unmatched
faces runs as a **nightly job**; admins can tune minimum detection score, maximum recognition
distance, and minimum recognized faces, then re-run recognition library-wide.
**No pet recognition** — it is one of Immich's most-requested open feature discussions (#7151,
#14442, #14981, #19689, #20526), which is precisely the gap this project exists to fill.

*What it does better than us:* zero-label clustering, merge, bulk assignment, detach as a negative
signal, admin-tunable thresholds, automatic re-recognition, and results that land in the **native
People surface and search** rather than in albums.

### Apple Photos — "it already did it"
Fully automatic on-device clustering into the **People & Pets** album, which recognizes **cats and
dogs** as first-class subjects (the only mainstream competitor that does). The user names a
suggestion; **Confirm Additional Photos** presents suggested matches for Yes/No adjudication;
**"X is Not in This Photo" / "Not This Person"** removes a wrong photo and feeds back as a
correction; duplicate clusters are **merged** by selecting and choosing Merge; people can be
**hidden**, **pinned**, or **featured less often**, which tunes Memories and the widget.
Zero configuration, zero pipeline concept, no thresholds, no jobs.

*What it does better than us:* everything about the first five minutes, and pets specifically.
*What it does worse:* no explanation of any decision, no export of the identity data, no operator
control, and it only works if the library lives in Apple's ecosystem.

### immich-pet-tagger — the direct competitor
The closest thing to us: YOLO + CLIP, local, Docker sidecar to Immich. The owner **enrolls a pet
with reference photos**; a **logistic-regression classifier** is trained on CLIP embeddings of
those references; an **hourly scan** crops, embeds, and matches new photos; matches are written
back as **Immich person tags**, so pets appear in Immich's native People section and search. Its
review UI supports finding candidate reference photos, marking **false positives**, reviewing
low-confidence matches, and — notably — a **dry-run "tagging accuracy" tool that reports recall and
false-positive rate** before committing to a full scan. Documented limitations: one pet per photo
when YOLO detects nothing, and hourly (not immediate) processing.

*What it does better than us:* results land in Immich's People surface instead of albums, it
measures its own accuracy including recall, and enrollment-from-reference-photos is a faster cold
start than queue review.
*What we do better:* durable review history and provenance, temporal weighting, species
correction, multi-pet photos, idempotent reclassification, job/backup/diagnostic operations, and
an explanation for every match.

---

## 5. Head-to-head by workflow stage

| Stage | Us today | Best in set | Gap |
|---|---|---|---|
| **Cold start** | Zero labels → everything Unknown; review 50–100 items by hand before automation begins | Apple/Immich/Lightroom all group unlabeled subjects automatically | **Severe.** We ask for the most work at the moment the owner has the least confidence the tool works |
| **Unit of work** | One crop | A cluster/stack of crops | **Severe.** Our labeling cost is O(photos); theirs is O(individuals) |
| **Confirmation throughput** | 1 per interaction (Review: keyboard 1–9/Space/S; Library: per-card dropdown) | Lightroom: whole stack; Immich: multi-select | **High.** Our keyboard shortcuts make each action fast but the count is still linear |
| **Wrong-identity correction** | Yes, any time, from Review or Library, reviewed or not (v1.4/FR-3) — **a genuine strength** | Apple "Not This Person", Immich detach | Parity on the happy path; we lack the *negative* signal (§6) |
| **Missed subject rescue** | **None.** If YOLO misses a dog, the photo is invisible to the system forever | Lightroom Draw Face Region; Immich assign unassigned face | **High and invisible** — we don't even measure it |
| **Identity hygiene** | Create, rename, activate/deactivate | Merge (Immich, Apple), split (requested in both) | **Medium.** No merge means a typo'd duplicate identity is permanent clutter |
| **Browse a subject** | Library filtered by identity; per-dog Insights (read-only) | A person page: cover, count, suggestions, actions | **Medium.** No single place that *is* "Fibs" |
| **Explainability** | Matched example, similarity, capture date, review reason badge | None of them show anything | **We win outright** |
| **Recompute** | Reclassify — explicit, idempotent, never touches reviewed labels; schedulable as a job operation | Immich nightly job; Apple continuous | **Low/medium.** Mechanism is better than theirs; it just doesn't trigger itself after new corrections |
| **Measurement** | Automation rate, confident coverage, per-species breakdown — over *detected crops only* | immich-pet-tagger reports recall + false-positive rate | **Medium.** Our numbers can look excellent while the library is half-tagged |
| **Where results live** | Immich albums (`Dog - Fibs`), with stale-membership cleanup on re-sync | Immich person tags (pet-tagger), native People (Apple/Immich) | **Medium.** Albums are a second-class surface in Immich's own UI |
| **Trust/safety** | Backups, validated restore, diagnostics, job cancel, WAL, provenance | None of them have an equivalent | **We win outright** |

---

## 6. Where we win (protect these)

1. **Ground truth that survives.** ADR-001 makes `state.db` authoritative; a correction is
   permanent, attributed, and never overwritten by reclassification. In Apple and Immich, the
   equivalent state is an implementation detail of a clustering algorithm that can be re-run.
2. **Every decision is explainable.** Which example matched, how similar, when that example was
   taken, and why the item is in review (`unknown` / `low-confidence` / `candidate-conflict` /
   `temporal-mismatch`). No competitor shows a user *why*.
3. **Time as evidence.** v1.5's per-example temporal weighting handles the cases that actually
   break pet libraries: a dog aging out of its own reference photos, a pet that has passed away,
   and a visually similar successor. Immich has birthdays; nobody else uses date as a *matching*
   signal.
4. **Species correction.** Dog↔cat confusion is a real YOLO failure mode and we're the only tool
   with a first-class fix that rescores against the corrected pool.
5. **Operational seriousness.** Backups, validated restore, diagnostics, stuck-job detection, job
   cancellation, batched commits, WAL. This is the difference between a weekend script and
   something an owner trusts with ten years of photos.
6. **Correct-any-time, including already-reviewed items,** with Immich album membership actually
   reconciled afterward (DT-1113). Apple and Immich handle their own equivalents; the pet-adjacent
   tools do not.

---

## 7. Where we lose (ranked, with evidence)

**G1 — Cold start is a wall.** *Evidence:* [docs/workflow.md §1–2](workflow.md); with zero
examples, `IdentityClassifier` has nothing to match and every crop is Unknown. *Impact:* the owner
must do 50–100 unassisted, unbatched corrections before the product does anything they couldn't do
themselves. Every competitor shows grouped, nameable subjects on first run. This is where trial
users quit.

**G2 — No bulk or cluster-level action anywhere.** *Evidence:* `ReviewPage` acts on one item;
`LibraryEntryCard` exposes a single `<select>` per card; no multi-select exists in `ui/src`; the
species-correction spec explicitly lists bulk as a non-goal. *Impact:* labeling cost scales with
photos, not with pets. Lightroom's "type a name on a stack" is the benchmark.

**G3 — No negative feedback.** *Evidence:* review actions are `SKIP` and `CORRECT`; Unknown is an
identity assignment, not a rejection. *Impact:* the owner cannot say "this is definitely *not*
Hermann." Apple, Immich, and pet-tagger all capture rejection, which is the cheapest possible
signal for separating lookalikes — exactly our hardest case.

**G4 — Missed detections are permanently invisible.** *Evidence:* nothing in the pipeline creates a
crop outside YOLO detection; there is no manual region or "tag this photo as Fibs" path.
*Impact:* recall is silently capped by the detector, and Lightroom's Draw Face Region shows the
expected escape hatch. Compounds with G5.

**G5 — We measure precision-ish, never recall.** *Evidence:* `services/metrics.py` computes
automation rate and confident coverage over `CropClassification` rows — i.e. only over photos where
detection already succeeded. *Impact:* the Metrics tab can read 95% while a large fraction of the
owner's actual dog photos were never detected. immich-pet-tagger explicitly reports recall; we
should not be behind a sidecar project on honesty about our own accuracy.

**G6 — No person-centric surface.** *Evidence:* Library is a filtered photo grid; Insights is
deliberately a read-only fun layer. *Impact:* the mental model shift v1.4 set out to make ("a
library I trust, not a queue I cleared") stopped one step short — the object the owner cares about
is the *pet*, and there is no page where a pet's tagging state and its pending decisions live
together.

**G7 — No merge (or split) of identities.** *Evidence:* `DogService` offers create/rename/activate
only. *Impact:* a duplicate or misspelled identity can be deactivated but never reconciled, and its
learned examples are stranded. Both Immich and Apple treat merge as table stakes.

**G8 — Results land in albums, not Immich's People surface.** *Evidence:* `SyncService` +
`AlbumService` create `Dog - <name>` albums. *Impact:* in Immich's own UI, People is the
identity-shaped surface with search integration; albums are a flat list users scroll past. The
directly competing sidecar writes person tags instead — worth understanding why before dismissing.

**G9 — The confidence threshold is a code constant.** *Evidence:* `policy.py`
`confident_threshold = 0.80`, no config, no per-identity override. *Impact:* an owner with three
lookalike dogs and an owner with one dog and one cat need different aggressiveness. Immich exposes
exactly these knobs to admins. (Centralizing the policy was right; not exposing *any* of it is the
gap.)

**G10 — Reclassify doesn't chase the owner's work.** *Evidence:* it is a manual Overview action —
schedulable as a job operation, but nothing triggers it after a review batch. *Impact:* the owner
has to know to click it to see their own progress; Apple and Immich re-recognize on their own.

---

## 8. Recommendations

Sequenced by impact per unit of effort. Each would start as a spec in `docs/specs/` and an issue,
per [CLAUDE.md](../CLAUDE.md).

### P0 — Close the cold start (addresses G1, G2, G6)
**"Name a group" — cluster the unlabeled crops and let one name label all of them.**
We already compute and store an OpenCLIP embedding for every crop; clustering them is a read-side
operation over data on disk, requiring no new model, no new pipeline stage, and no change to
classification policy. Ship it as a new surface (Library filter or its own view) that shows
unlabeled crops grouped by visual similarity, with a single naming action per group that fans out
to N `CORRECT` actions through the existing `ClassificationCorrectionService` — so every resulting
label is ordinary ground truth with ordinary provenance.

This converts the first session from "review 50–100 photos one at a time" to "name three groups,"
which is the workflow all three faces competitors actually ship. It is also the enabling step for
G2 (bulk) and a natural home for G6 (a per-pet surface).

*Risks to design around:* an impure cluster must be splittable/partially rejectable before naming
(otherwise one action writes bad ground truth at scale); clustering must never write predictions or
manufacture confidence — it proposes groupings, humans decide. Both are consistent with our
existing "no manufactured confidence" rule.

### P1 — Multi-select and negative feedback (G2, G3)
- **Multi-select in Library** with "assign selected to <identity>" — the endpoint already exists;
  this is selection state plus a batched call.
- **A "not this one" action** on review and library items, stored as a review action and used to
  suppress the rejected identity for that crop. Small data change, disproportionate value for
  lookalike dogs, and it matches the affordance all three competitors ship.

### P1 — Tell the truth about recall (G5)
Add a coverage number that counts photos where a pet was detected against a defensible denominator
(e.g. assets scanned, with an explicit statement of what the denominator means), and surface
detection failures as a category rather than an absence. Follow immich-pet-tagger's example of
reporting the unflattering number. This is cheap, honest, and directly serves the "trustworthy
library" positioning.

### P2 — A pet page (G6)
Promote per-dog Insights into a full pet home: cover crop, confirmed/auto/pending counts, "photos
needing your decision for this pet," rename, and the merge action below. Reuses existing endpoints
almost entirely; it is an information-architecture change more than a feature.

### P2 — Merge identities (G7)
`DogService.merge(source, target)`: reassign classifications, re-file embedding examples, record
provenance, and let the next sync reconcile albums (the DT-1113 stale-membership machinery already
handles the album side). Table stakes against Immich and Apple.

### P2 — Rescue missed detections (G4)
The cheapest useful version is not Lightroom's draw-a-region: it is **"this photo contains <pet>"**
from an asset that produced no crop — enough to add a reference example and to make the photo
album-eligible. Full manual region drawing is a larger UI investment; scope it separately if the
recall number from P1 says it matters.

### P3 — Owner-facing sensitivity (G9) and auto-reclassify (G10)
A single "how cautious should automatic tagging be" control mapping to the existing policy
threshold, and an automatic Reclassify trigger after a review batch settles. Both are small; both
are polish relative to P0–P2.

### Explicitly *not* recommended
- **Don't chase Apple's zero-configuration magic wholesale.** Our operator controls, jobs, and
  diagnostics are a differentiator for the self-hosting owner, not debt.
- **Don't drop the review queue.** v1.4 already settled this: it is the triage view, not the
  product.
- **Don't replace album sync with person-tag sync (G8) without a decision.** Writing pets into
  Immich's People surface is what the competing sidecar does and it is genuinely better for search,
  but it means writing into a namespace Immich owns and reconciling against its own face
  recognition. This deserves an ADR, not a patch. Offering it as an *additional* sync target is the
  low-risk framing.
- **Don't add cloud anything.** Local-only is a stated principle and a genuine competitive
  advantage against every non-self-hosted option here.

---

## 9. Open questions for the owner

1. Is **speed to first value** worth the P0 investment, or is the current 50–100-item cold start
   acceptable because the owner has already paid it once? (It matters if this project is ever
   shared with other Immich users — and Immich's five open pet-recognition discussions say there
   is an audience.)
2. Should confirmed pets appear in **Immich's People surface** as well as albums? This is the
   single biggest divergence from the directly competing tool.
3. Is a **negative label** ("not Hermann") acceptable under our ground-truth model, or does it
   complicate the "a human review is authoritative input" invariant more than it's worth?
4. What is the honest **denominator** for a recall metric in a library where most photos legitimately
   contain no pets?

---

## 10. Sources

Competitor behavior verified August 2026:

- Immich facial recognition docs — https://github.com/immich-app/immich/blob/main/docs/docs/features/facial-recognition.md and https://docs.immich.app/features/facial-recognition/
- Immich pet-recognition feature discussions — [#7151](https://github.com/immich-app/immich/discussions/7151), [#14442](https://github.com/immich-app/immich/discussions/14442), [#14981](https://github.com/immich-app/immich/discussions/14981), [#19689](https://github.com/immich-app/immich/discussions/19689), [#20526](https://github.com/immich-app/immich/discussions/20526)
- Immich face unassign/detach discussions — [#5276](https://github.com/immich-app/immich/discussions/5276), [#13221](https://github.com/immich-app/immich/discussions/13221), [#28394](https://github.com/immich-app/immich/discussions/28394)
- `immich-pet-tagger` — https://github.com/tedornitier/immich-pet-tagger
- Adobe, "Use Intelligent facial recognition in Lightroom Classic" — https://helpx.adobe.com/lightroom-classic/help/face-recognition.html
- Adobe community threads on animal face detection in Lightroom Classic — https://community.adobe.com/t5/lightroom-classic-discussions/when-lightroom-will-start-detect-animals-faces-food-and-ext/m-p/8847960
- Apple, "Find and name photos of people and pets on Mac" — https://support.apple.com/guide/photos/find-and-name-people-and-pets-phtad9d981ab/mac
- Apple, "Find People and Pets in Photos on your iPhone or iPad" — https://support.apple.com/en-us/108795
