# Immich Dog Tagger

Immich Dog Tagger finds dogs (and cats) in your [Immich](https://immich.app/) photo library,
learns to tell individual animals apart from photos you review, and syncs the results back to
Immich as albums.

![immich-dog-tagger project banner](banner.png)

If your library has thousands of photos of the same few pets across years of lighting, cameras,
and angles, tagging them by hand doesn't scale. This project detects each animal, asks you to
confirm or correct its first guesses, and gets better at recognizing that animal every time you
do. Everything runs on your own machine — no photo ever leaves it.

## Screenshots

| Review | Library | Overview |
|---|---|---|
| ![Review UI](docs/images/review-ui.png) | ![Library UI](docs/images/library-ui.png) | ![Overview UI](docs/images/overview-ui.png) |

The review workspace has keyboard shortcuts for fast correction (one key per identity, plus
`u` for Unknown), a queue filterable by unknown/low-confidence/candidate-conflict, and shows each
match's ranked candidates, similarity score, and the photo's own capture date.

## Quick start

Requirements: Python 3.14+, [`uv`](https://docs.astral.sh/uv/), Node.js/npm, and a running Immich
instance with an API key. See [Requirements](#requirements) for hardware notes.

1. **Bootstrap dependencies.**

   ```bash
   ./scripts/bootstrap.sh
   ```

2. **Configure your Immich connection.** Copy `.env.example` to `.env` and fill in `IMMICH_URL`
   and `IMMICH_API_KEY`.

   ```bash
   cp .env.example .env
   ```

3. **Run the pipeline once.** This scans your library, downloads new photos, detects dogs/cats,
   and classifies each one.

   ```bash
   immich-dog-tagger scan
   immich-dog-tagger download
   immich-dog-tagger detect
   immich-dog-tagger classify
   ```

   Expect almost everything to come back Unknown on this first run — there are no reference
   examples yet. That's normal, not a bug.

4. **Start the backend, then the frontend** (two terminals):

   ```bash
   uv run uvicorn immich_dog_tagger.api.app:app --reload
   ```

   ```bash
   cd ui && npm install && npm run dev
   ```

5. **Review.** Open `http://localhost:5173`, correct a batch of predictions (50-100 is a
   reasonable starting point), then click **Reclassify** in Overview to apply what you've
   learned to everything else. Repeat until the review queue is mostly gone.

6. **Publish to Immich** once you're happy with a batch of identities:

   ```bash
   immich-dog-tagger sync
   ```

For the full walkthrough — how many photos to review first, what "confident," "needs review," and
"unknown" mean, and how to back up `state.db` — see [docs/workflow.md](docs/workflow.md). For a
Docker + Traefik production setup, see [docs/deployment.md](docs/deployment.md).

## How it works

```
Immich → Scanner → Downloader → YOLO Detection → Crop Generation → OpenCLIP Embeddings
       → Identity Classification → Human Review → Learning Examples → Improved Classification
       → Immich Sync
```

1. **Detect.** YOLO finds dogs and cats in each photo and crops them out.
2. **Classify.** An OpenCLIP embedding of each crop is compared against your reviewed examples
   to guess an identity, or leave it unknown if nothing matches well enough.
3. **Review.** You confirm or correct guesses in a browser UI.
4. **Learn.** Each correction becomes a new reference example, and future guesses improve —
   no retraining, no model weights change.
5. **Sync.** Confirmed identities are published back to Immich as albums (`Dog - Hermann`,
   `Cat - Fibonacci`, ...).

`state.db`, a local SQLite database, is the source of truth for everything the system knows.
Immich is a photo source and a place to publish results — never the other way around. See
[ADR-001](docs/adr/ADR-001-state-database-source-of-truth.md) for why.

## Architecture

```
Browser → Traefik → React UI (nginx) → FastAPI → Application Services → state.db
                                                                              |
                                                                  +-----------+-----------+
                                                                  v                       v
                                                            ML Pipeline              Immich Sync
```

- **CLI** (`src/immich_dog_tagger/cli.py`) — runs pipeline stages and automation:
  `scan`, `download`, `detect`, `classify`, `sync`, `backup`, `restore`, and more.
- **Application services** (`src/immich_dog_tagger/services/`) — the business logic for
  classification, correction, jobs, scheduling, sync, and learning. The API and UI call into
  these rather than embedding logic of their own.
- **FastAPI** (`src/immich_dog_tagger/api/`) — the review, jobs, schedules, dogs/cats, and
  diagnostics endpoints behind the browser UI.
- **React UI** (`ui/src/`) — the review workspace, the Library, and the Overview dashboard.
- **ML pipeline** — YOLO detection, cropping, OpenCLIP embeddings, and nearest-neighbor
  classification. See [docs/ml-classification.md](docs/ml-classification.md).
- **state.db** — assets, detections, crops, classifications, identities, reference examples,
  review history, provenance, jobs, and schedules, in SQLite.

On disk, a project looks like this:

```
data/breimer/
├── state/
│   └── state.db      # knowledge: cannot be regenerated, back it up
└── cache/
    ├── assets/        # rebuildable
    ├── crops/         # rebuildable
    └── review/         # rebuildable
```

## Requirements

- Python 3.14+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js (for the UI) and `npm`
- An Immich instance with API access
- A GPU is recommended for detection and embedding — CPU works but is much slower

Developed and tested on Ubuntu with an NVIDIA GPU.

## Status: what to expect

Current release: **v1.4.0**. The core loop — detect, classify, review, learn, sync — is in daily
use on the maintainer's own library. Before you rely on it, know a few things:

- **It's a solo-maintained hobby project.** Development happens in bursts, not on a schedule.
- **No authentication on the API or UI.** Run it on a trusted network behind your own reverse
  proxy, not exposed to the internet.
- **Confidence isn't a calibrated probability.** It's a similarity score against your own
  reviewed examples, not a validated accuracy estimate. See
  [docs/ml-classification.md](docs/ml-classification.md).
- **Large-library performance is validated with synthetic-scale tests, not a real 30,000-photo
  run.** The pipeline is built to handle libraries that size, but if yours is that large, expect
  to be an early real-world test of it.
- **One pipeline or Reclassify operation runs at a time**, by design — queue a second one and it
  waits rather than running in parallel.

See [docs/status.md](docs/status.md) for current known issues and what's actively in progress,
and [docs/roadmap.md](docs/roadmap.md) for release history. Recent releases:

- **v1.4.0 — Trustworthy photo library.** Every photo shows its own capture date next to its
  prediction. A new Library page lists every classified photo — reviewed or not — filterable by
  identity, species, review status, and date. Corrections work the same way from the Library as
  from Review, and now correctly move an asset between Immich albums instead of leaving it in
  both. Identities can have an optional active date range, and a match outside that range is
  flagged, never silently accepted. Details:
  [docs/specs/v1.4-trustworthy-photo-library.md](docs/specs/v1.4-trustworthy-photo-library.md).
- **v1.3.0 — Cat support.** Detection, classification, review, and sync now cover cats alongside
  dogs, sharing one review queue and correction UI — no separate cat mode. Details:
  [issue #66](https://github.com/bradreimer/immich-dog-tagger/issues/66).
- **v1.2.0 — Visual style refresh.** One consistent look across the app: sidebar navigation, a
  single accent color, a shared stat-tile/chart pattern. Details:
  [docs/specs/v1.2-visual-style-refresh.md](docs/specs/v1.2-visual-style-refresh.md).

## Development

```bash
./scripts/bootstrap.sh   # fresh environment
uv run pytest -q         # tests
./scripts/check.sh       # full validation (Python + UI)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request, and
[CLAUDE.md](CLAUDE.md) for the spec/ticket-driven workflow this project follows.

## Design goals

This project stays deliberately small:

- No cloud AI services, and no photo or image data ever leaves your machine
- No modifying Immich internals — Immich is only ever a source and a sync target
- No retraining a neural network — "learning" means growing a set of reference examples, not
  updating model weights

## License

See [LICENSE](LICENSE).
