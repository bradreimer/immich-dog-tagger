# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

Immich Dog Tagger scans an Immich photo library, detects dogs (YOLO), generates crops and
OpenCLIP embeddings, and classifies individual dog identities using nearest-neighbor similarity
against a locally learned reference set. Humans review uncertain predictions in a browser UI;
corrections become new reference examples (active learning). Results are synced back to Immich
as albums.

Core principle: **`state.db` is the source of truth.** Immich is a photo source and a
presentation/export target only — never the authoritative store for application state, review
history, or learned examples. See [docs/adr/ADR-001-state-database-source-of-truth.md](docs/adr/ADR-001-state-database-source-of-truth.md).

```
Immich → Scanner → Downloader → YOLO Detection → Crop Generation → OpenCLIP Embeddings
       → Identity Classification → Human Review → Learning Examples → Improved Classification
       → Immich Sync
```

## Spec-driven, ticket-driven development

This is the required workflow — follow it before writing code for any meaningful change:

1. Check [docs/specs/](docs/specs/) for an existing spec covering the behavior. If none exists
   for a user-facing or cross-cutting change, write one first (template in
   [docs/specs/README.md](docs/specs/README.md): Purpose, User story, Goals, Non-goals,
   Requirements, Acceptance criteria, Open questions).
2. Check [docs/tickets/](docs/tickets/) for an implementation-sized ticket. Create one if it
   doesn't exist (template in [docs/tickets/README.md](docs/tickets/README.md): ID, Related spec,
   Priority, Status, Goal, Context, Implementation notes, Acceptance criteria, Testing
   requirements, Dependencies, Suggested commit message).
3. Implement in small, focused commits with tests.
4. Update [docs/status.md](docs/status.md) and the relevant spec/ticket as progress changes.
5. Record significant architectural decisions as an ADR in [docs/adr/](docs/adr/) (Status,
   Context, Decision, Alternatives Considered, Consequences).

The current milestone and active work are tracked in [docs/status.md](docs/status.md) and
[docs/roadmap.md](docs/roadmap.md). The in-flight release spec is
[docs/specs/v1.0.0.md](docs/specs/v1.0.0.md), backed by tickets `DT-1000`–`DT-1011` in
[docs/tickets/](docs/tickets/).

## Architecture

- **CLI** (`src/immich_dog_tagger/cli.py`) — operational interface for pipeline stages and
  automation (`scan`, `download`, `detect`, `classify`, `sync`, ...).
- **Application services** (`src/immich_dog_tagger/services/`) — business logic: classification,
  correction, jobs, pipeline orchestration, scheduler, sync, dogs, backup, learner. The API and
  UI must go through these services rather than embedding business logic or raw SQLAlchemy
  queries in routes/components.
- **FastAPI** (`src/immich_dog_tagger/api/`, routes in `api/routes/`) — human interaction layer:
  review, jobs, schedules, dogs, crops, embedding examples, diagnostics, health.
- **React UI** (`ui/src/`, features in `ui/src/features/`: `review/`, `jobs/`, `dogs/`,
  `metrics/`, `overview/`) — browser review workspace and Overview operational dashboard.
- **ML pipeline** — YOLO detection (`detector.py`, `yolo_detector.py`), cropping (`crops.py`),
  OpenCLIP embeddings (`embedder.py`, `openclip_embedder.py`), classification (`classifier.py`,
  `scoring.py`).
- **state.db** (SQLite via SQLAlchemy, `database.py`, `models.py`) — assets, detections, crops,
  classifications, identities, embedding examples, review actions, provenance, jobs, schedules.

Keep these layers separate — see [docs/project-overview.md](docs/project-overview.md) and
`CONTRIBUTING.md`'s "Architecture Principles" section for the full rationale.

For the active-learning design: [docs/adr/ADR-002-active-learning-architecture.md](docs/adr/ADR-002-active-learning-architecture.md)
and [docs/ml-classification.md](docs/ml-classification.md).

## Working conventions

- Prefer small, composable changes over rewrites. Reuse an existing service, model, or component
  before introducing a new abstraction.
- Strong typing, clear names, explicit behavior, thin I/O boundaries. Avoid clever abstractions.
- Database changes deserve extra care: `state.db` holds accumulated review/learning history that
  cannot be regenerated (cache/crops can be rebuilt; the database cannot). Prefer migrations over
  destructive schema edits and consider existing databases, not just fresh installs.
- Ground truth vs. predictions: a human review is authoritative input; a classifier recommendation
  is derived, reproducible state. Reclassification must never mutate reviewed labels (see
  [docs/specs/v1.0.0.md](docs/specs/v1.0.0.md) FR-4/FR-5 and the "Responsible architectural
  guidelines" section for the fuller policy: idempotency, no manufactured confidence, validate at
  boundaries, bound resources, keep ML policy centralized).
- Privacy: this stays local-first. Never send image data or personal photo metadata to external/
  cloud services, and don't log image contents, credentials, or unnecessary personal metadata.
- One logical change per commit; commit messages describe intent (`feat(review): ...`,
  `fix(api): ...`), not vague descriptions like "fix stuff".

## UI conventions

Full guidance: [docs/specs/ux-principles.md](docs/specs/ux-principles.md). Key points to apply
when touching `ui/`:

- Reuse existing components/patterns before creating new ones; one consistent visual language app-wide.
- Icon library is Tabler (`@tabler/icons-react`) only. Icon-only buttons need `aria-label`.
- Action buttons use the shared orange action color language and a consistent hover treatment;
  non-action surfaces (cards, rows, panels) should not have hover animation.
- Prioritize the review workflow: keyboard-friendly, minimal navigation, obvious next action,
  immediate feedback, minimal confirmation dialogs for non-destructive actions.
- Destructive/irreversible actions get distinct styling and, where warranted, confirmation.
  Prefer reversible designs (skip over delete, etc.).
- Priority when principles conflict: correctness > clarity > speed > consistency > visual polish.

## Validation before considering work done

Python:
```bash
uv run ruff check --fix .
uv run ruff format
uv run pytest -q
```

UI (from `ui/`):
```bash
npm run build
npm run lint
```

Combined project validation script: `./scripts/check.sh`. Fresh environment bootstrap:
`./scripts/bootstrap.sh`.

For UI-affecting changes, also run the dev servers and exercise the change in a browser — the
backend serves at `http://localhost:8000` (`uv run uvicorn immich_dog_tagger.api.app:app --reload`)
and the frontend at `http://localhost:5173` (`cd ui && npm run dev`, proxies `/api`).

## Key docs map

- [docs/project-overview.md](docs/project-overview.md) — purpose, vision, design principles, stack.
- [docs/roadmap.md](docs/roadmap.md) / [docs/status.md](docs/status.md) — planning and current state.
- [docs/development-workflow.md](docs/development-workflow.md) — idea → spec → ticket → implementation → tests → docs → commit → release.
- [docs/deployment.md](docs/deployment.md) — Docker Compose, Traefik, nginx, scheduler operation.
- [docs/ml-classification.md](docs/ml-classification.md) — classification pipeline detail.
- [docs/project-health.md](docs/project-health.md) — known risks and gaps.
- [docs/adr/](docs/adr/) — architectural decisions.
- [docs/specs/](docs/specs/), [docs/tickets/](docs/tickets/) — behavioral specs and implementation-sized work.
- `CONTRIBUTING.md` — contribution conventions (this file summarizes the parts most relevant to
  automated changes; consult it directly for anything not covered here).
