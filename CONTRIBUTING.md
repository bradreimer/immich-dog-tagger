# Contributing to Immich Dog Tagger

Thanks for your interest in contributing to Immich Dog Tagger! 🐕

Immich Dog Tagger is a small, open-source side project for detecting individual dogs in an Immich photo library, learning from human corrections, and keeping those classifications synchronized back to Immich.

The project is still evolving, so contributions are very welcome. You don't need to be an expert in machine learning, Immich, or the entire codebase to help. Bug reports, documentation improvements, UI polish, tests, and small improvements are all valuable.

This guide explains how to get started and the conventions that help keep the project maintainable.

**NOTE:** This is a hobby project. There is no team, only me.

## Before You Start

For larger changes, please open an issue first or start a discussion before writing a lot of code.

This is especially useful for:

* New features
* Changes to the database model
* Changes to the classification or learning system
* Changes to the CLI
* Changes to the API
* Changes to the overall architecture

For small fixes, documentation changes, tests, and obvious improvements, feel free to open a pull request directly.

If you're not sure whether an idea fits the project, that's perfectly fine. Open an issue and describe what you're thinking.

## Development Environment

The project currently uses:

* Python 3.14+
* [`uv`](https://docs.astral.sh/uv/)
* SQLite
* pytest
* Ruff
* FastAPI
* React + TypeScript
* Vite
* Docker for deployment
* NVIDIA GPU acceleration for local AI inference when available

A fresh development environment can be bootstrapped with:

```bash
./scripts/bootstrap.sh
```

Then install the Python dependencies:

```bash
uv sync
```

The project README contains additional information about running the backend, frontend, and processing pipeline locally.

## Running the Tests

The fastest way to run the Python test suite is:

```bash
uv run pytest -q
```

The project also provides a validation script:

```bash
./scripts/check.sh
```

Before submitting a pull request, please make sure the relevant checks pass.

For Python changes, the usual development workflow is:

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

If you're making a change that affects both backend and frontend code, run the complete validation script as well.

## How to Make Changes

The project favors **small, focused changes**.

A good pull request usually:

* Solves one problem
* Makes the smallest reasonable change
* Includes tests for new or changed behavior
* Reuses existing patterns
* Avoids unrelated refactoring
* Leaves the project in a working state

Please inspect the existing code and tests before introducing a new abstraction. There is usually an existing service, model, helper, or test fixture that can be extended.

In particular, avoid combining a feature with a large unrelated refactor. Smaller changes are easier to review, test, and revert.

### One Logical Change Per Commit

The project generally prefers commits that each represent one logical change.

For example:

```text
Add candidate-conflict review filtering
Add tests for candidate-conflict filtering
Improve review queue documentation
```

is preferable to one large commit containing all three plus an unrelated database refactor.

This isn't a rigid rule, but focused commits make the project's history much easier to understand.

## Architecture Principles

There are a few architectural principles that are particularly important to this project.

### `state.db` Is the Source of Truth

The local SQLite database is the system of record.

It owns:

* Processing state
* Detections
* Crops
* Classifications
* Identities
* Review history
* Learned examples
* Provenance

Immich is treated as the **photo source and presentation/export target**.

In other words:

```text
Immich
   ↓
Dog Tagger
   ↓
state.db
   ↓
ML pipeline / Review UI
   ↓
Immich sync
```

Please avoid designs that make Immich responsible for application state or require the application to reconstruct its knowledge from Immich.

### Keep Layers Separate

The project intentionally separates:

* CLI operations
* Application services
* Database/state management
* ML processing
* FastAPI
* React UI
* Immich synchronization

The API and UI should generally use application services rather than implementing business logic themselves.

Similarly, database access should remain behind appropriate service/repository boundaries rather than leaking SQLAlchemy queries throughout API routes or UI-facing code.

### Prefer Simple, Explicit Code

This project values:

* Strong typing
* Clear names
* Small services
* Dependency injection
* Explicit behavior
* Testable logic
* Thin I/O boundaries

Avoid clever abstractions when a straightforward implementation is easier to understand.

The goal is not to build the most elaborate ML platform imaginable. The goal is to build a small, reliable local assistant that does one useful thing well.

## Data and Privacy

Immich Dog Tagger is designed around keeping personal photo data local.

Please do not introduce functionality that:

* Uploads personal photos to external services
* Sends image data to cloud AI services
* Collects personal photo metadata unnecessarily
* Stores secrets or credentials in the repository

Changes involving external services or data transmission should be discussed before implementation.

## Machine Learning Changes

The project uses local computer vision and embedding models to detect and classify dogs.

The current learning approach uses confirmed examples and embedding similarity rather than retraining a large neural network.

If you're changing classification or learning behavior, please include tests where practical and explain the behavioral change in the pull request.

ML changes can be particularly difficult to evaluate from unit tests alone, so please distinguish between:

* Changes to deterministic application logic
* Changes to model configuration
* Changes to classification behavior
* Changes that require real-world image evaluation

Don't assume that a more complicated model or training pipeline is automatically an improvement.

## Database Changes

Database changes deserve extra care because `state.db` contains the project's accumulated knowledge.

When changing models or persistence behavior:

* Consider existing databases, not just fresh installations
* Preserve existing data where possible
* Make migrations or compatibility behavior explicit when necessary
* Avoid destructive changes without discussion
* Add tests for important persistence behavior

Remember that cached assets and crops can generally be rebuilt. The knowledge stored in the database is considerably more important.

## UI Changes

The web UI is primarily a human review and correction interface.

When making UI changes, please consider:

* Keyboard-friendly workflows
* Clear review states
* Loading and empty states
* Error handling
* Small-screen layouts
* Keeping business logic in the backend/application layer

A UI change should ideally make the review workflow clearer or faster rather than simply adding more controls.

## Tests

New behavior should normally come with tests.

Tests are particularly important for:

* Classification logic
* Review queue behavior
* Database operations
* API behavior
* CLI behavior
* Data transformations
* Edge cases

When fixing a bug, a regression test is strongly preferred.

You don't need to test every line of code. Focus on protecting behavior that matters.

## Pull Requests

A good pull request should explain:

1. **What changed**
2. **Why it changed**
3. **How it was tested**
4. **Anything reviewers should pay particular attention to**

For example:

```text
## Summary

Adds candidate-conflict filtering to the review queue.

## Why

Images where the top candidates are very close are particularly
useful for human review.

## Testing

- ./scripts/check.sh
```

Keep pull requests focused. If you discover an unrelated improvement while working, consider opening a separate issue or pull request rather than expanding the current change.

## Commit Messages

There is no elaborate commit-message bureaucracy here.

Prefer short, descriptive messages that explain the intent of the change:

```text
Add review queue candidate filtering
Fix review correction provenance
Add API tests for skipped reviews
Improve review progress display
```

Avoid messages such as:

```text
fix stuff
changes
updates
wip
```

## Reporting Bugs

When reporting a bug, please include enough information to reproduce it.

Useful details include:

* What you expected to happen
* What actually happened
* The command or UI action involved
* Relevant error messages
* Project version or commit
* Python/Node versions where relevant
* Whether the issue occurs with a fresh database
* Steps to reproduce the problem

Please don't upload personal photographs or other private Immich data to an issue.

If an example image is genuinely necessary to explain an ML problem, describe the characteristics of the image first and avoid sharing personally identifying material.

## Feature Requests

Feature requests are welcome.

A useful feature request explains the problem before proposing the solution:

```text
Problem:
What is difficult or impossible today?

Current behavior:
What happens now?

Desired behavior:
What would make this better?

Why:
Why is this useful?
```

This helps avoid prematurely committing the project to a particular implementation.

## What Makes a Good Contribution?

Not every contribution needs to be a major feature.

Some particularly useful contributions include:

* Fixing a bug
* Adding a missing test
* Improving error handling
* Improving documentation
* Making the review UI easier to use
* Improving accessibility
* Improving performance
* Simplifying confusing code
* Improving deployment documentation
* Reproducing and diagnosing an issue
* Reviewing an existing pull request

If you find something confusing, that's useful information too. A confusing part of the project may be a documentation problem or a design problem.

## A Note About This Project

Immich Dog Tagger is maintained as a personal side project.

That means development may sometimes happen in bursts, and pull requests or issues may not receive an immediate response. Please don't interpret a quiet period as a lack of interest.

The project is intentionally kept relatively small and focused. Not every reasonable feature will necessarily fit the project's direction.

Contributions are appreciated, but the goal is sustainable development rather than trying to turn this into a giant framework.

## Code of Conduct

Please be respectful and constructive.

Assume good intentions, discuss technical disagreements directly, and remember that everyone contributing is giving some of their time to make the project better.

Harassment, personal attacks, discrimination, and other inappropriate behavior are not welcome.

## License

By contributing to this repository, you agree that your contributions will be licensed under the same license as the project.

See [LICENSE](LICENSE) for details.

## Thank You

Whether you're fixing a typo, reporting a bug, improving the UI, writing tests, or building something substantial, thanks for helping make Immich Dog Tagger better.

And yes, the dogs will probably take credit for the work. 🐶
