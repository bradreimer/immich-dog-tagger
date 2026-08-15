# Contributing to Immich Dog Tagger

Thanks for your interest in contributing. Immich Dog Tagger is a small, open-source project for
detecting individual dogs and cats in an Immich photo library, learning from human corrections,
and syncing those identities back to Immich.

This is a hobby project maintained by one person, not a team. Bug reports, documentation fixes,
UI polish, tests, and small improvements are all useful — you don't need ML or Immich expertise
to help.

## Before you start

For larger changes — new features, database model changes, changes to classification or
learning, or changes to the CLI, API, or overall architecture — open an issue first. It saves you
from writing code that goes in a direction the project doesn't want.

For small fixes, documentation, tests, and obvious improvements, open a pull request directly.

If you're unsure whether an idea fits, open an issue and describe it. That's what issues are for.

## Development environment

- Python 3.14+ and [`uv`](https://docs.astral.sh/uv/)
- SQLite
- FastAPI, React, TypeScript, Vite
- Docker for deployment
- An NVIDIA GPU for local inference, if you have one

Bootstrap a fresh environment:

```bash
./scripts/bootstrap.sh
uv sync
```

See the [README](README.md) for running the backend, frontend, and processing pipeline locally.

## Running the tests

```bash
uv run pytest -q
```

Before opening a pull request:

```bash
uv run ruff check --fix .
uv run ruff format
uv run pytest -q
```

For UI changes:

```bash
cd ui
npm run build
npm run lint
```

If your change touches both backend and frontend, run `./scripts/check.sh` too.

## Making changes

Favor small, focused pull requests. A good one:

- Solves one problem
- Makes the smallest reasonable change
- Includes tests for new or changed behavior
- Reuses an existing service, model, or component instead of adding a new one
- Doesn't bundle in an unrelated refactor

Look at the existing code and tests before introducing a new abstraction — there's usually
something to extend already.

### One logical change per commit

Prefer several small commits over one large one:

```text
Add candidate-conflict review filtering
Add tests for candidate-conflict filtering
Update review queue documentation
```

This isn't a hard rule, but it keeps the project history readable.

## Architecture principles

### `state.db` is the source of truth

The local SQLite database owns processing state, detections, crops, classifications,
identities, review history, and provenance. Immich is a photo source and a sync target — it does
not hold application state, and the app never reconstructs its knowledge from Immich.

```
Immich → Dog Tagger → state.db → ML pipeline / Review UI → Immich sync
```

Avoid designs where Immich becomes responsible for state the app needs to remember.

### Keep layers separate

CLI, application services, the database layer, ML processing, the API, the UI, and Immich sync
each have a job. The API and UI call into application services rather than implementing business
logic themselves, and database access stays behind those services instead of leaking SQLAlchemy
queries into routes or components.

### Prefer simple, explicit code

Strong typing, clear names, small services, explicit behavior, thin I/O boundaries. Skip a clever
abstraction when a straightforward implementation reads just as easily. The goal isn't an
elaborate ML platform — it's a small, reliable local tool that does one thing well.

## Data and privacy

This project is local-first by design. Don't add code that:

- Uploads photos or image data to an external or cloud service
- Sends photo metadata anywhere it doesn't need to go
- Stores secrets or credentials in the repository

Discuss any change involving external services before implementing it.

## Machine learning changes

Classification uses embedding similarity against confirmed examples, not a retrained neural
network — a more complex model or training pipeline isn't automatically an improvement.

Unit tests can't tell you everything about an ML change, so when you open a PR, be clear about
what kind of change it is: deterministic application logic, model configuration, classification
behavior, or something that needs real-world image evaluation to judge.

## Database changes

`state.db` holds the project's accumulated review history and learned examples — data that can't
be regenerated (cached assets and crops can be). When you change models or persistence:

- Consider existing databases, not just a fresh install
- Add a migration or explicit compatibility behavior rather than a destructive change
- Add tests for the persistence behavior that matters

## UI changes

The web UI is primarily a review and correction tool. Keep it keyboard-friendly, with clear
loading/empty/error states and a layout that works on a small screen. Keep business logic in the
backend. A good UI change makes the review workflow clearer or faster — not just more configurable.

## Tests

New behavior should come with tests, especially for classification logic, review queue behavior,
database operations, and API/CLI behavior. A bug fix should come with a regression test. You don't
need to test every line — focus on the behavior that matters.

## Pull requests

Explain what changed, why, how you tested it, and anything a reviewer should look at closely:

```text
## Summary
Adds candidate-conflict filtering to the review queue.

## Why
Images where the top candidates are very close are useful to review first.

## Testing
./scripts/check.sh
```

Keep pull requests focused. If you find an unrelated improvement while working, open a separate
issue or PR for it.

## Commit messages

Short and descriptive, explaining intent:

```text
Add review queue candidate filtering
Fix review correction provenance
Add API tests for skipped reviews
```

Not:

```text
fix stuff
changes
wip
```

## Reporting bugs

Include what you expected, what happened instead, the command or UI action involved, any error
messages, the project version or commit, and whether the issue reproduces with a fresh database.

Don't attach personal photos or private Immich data to an issue. If an example image is genuinely
needed to explain an ML problem, describe it instead of sharing anything identifying.

## Feature requests

Describe the problem before proposing a solution:

```text
Problem: what's difficult or impossible today?
Current behavior: what happens now?
Desired behavior: what would be better?
Why: why does this matter?
```

This keeps the project from committing to a specific implementation too early.

## What makes a good contribution

Not every contribution needs to be a feature. Bug fixes, missing tests, better error handling,
documentation fixes, accessibility improvements, and diagnosing an existing issue are all
valuable. If something in the project confused you, that's useful signal too — it's either a
documentation gap or a design problem.

## A note about this project

Development happens in bursts, since this is a side project. A quiet period on an issue or PR
isn't a lack of interest. The project stays intentionally small — not every reasonable feature
will fit its direction.

## Code of conduct

Be respectful and constructive. Assume good intentions, discuss disagreements directly.
Harassment, personal attacks, and discrimination aren't welcome here.

## License

By contributing, you agree your contributions are licensed under the same license as the project.
See [LICENSE](LICENSE).
