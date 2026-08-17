# Plan: a central spec registry with per-repo push/pull

How a team keeps specs living **in** each repository — reviewed alongside the code that implements
them — while a central group normalizes their shape, publishes shared standards, and gets a
cross-repo view.

![Spec lifecycle: the seven steps a change goes through in a repo, and the pull, push, and promote
flows between that repo and a central spec registry](spec-lifecycle.svg)

## 1. The problem

Specs want to be in two places at once.

**Locally**, because a spec that isn't next to the code goes stale within a month, can't be reviewed
in the same pull request as its implementation, isn't available offline, and can't be read by an
agent working in the repo.

**Centrally**, because a team wants one vocabulary and one shape across repos, wants org-wide
constraints (auth, logging, accessibility, data retention) written once instead of re-litigated per
repo, and wants to answer "has anyone already specced this?"

The three obvious answers each fail:

| Approach | Why it fails |
|---|---|
| Git submodule pointing at a central repo | Conflates read-only standards with repo-owned specs, breaks shallow clones and most CI, and every contributor has to learn submodule mechanics to edit a markdown file. |
| Specs live only in the central repo | Kills local-first. Spec and implementation land in different PRs at different times, and the spec is nobody's problem once it's merged. |
| Copy the templates around by hand | Works for a week. Drift is immediate, unmeasurable, and unfixable — nobody knows which repo is on which version. |

What actually works is the package-manager model: **vendor central content into each repo at a
pinned version, with a lockfile**, and publish a metadata index back up. Upgrades become ordinary
reviewable commits. Nothing is a runtime dependency.

## 2. Design principles

1. **One writer per file.** Every file has exactly one owner — the repo or the registry. The two
   sides never edit the same file, so sync is a copy, never a three-way merge. This single rule is
   what keeps the whole system from becoming a distributed-state problem.
2. **Local-first.** Everything needed to do the work is committed in the repo. Sync is a periodic
   refresh, never a dependency of building, testing, or reviewing. Registry unreachable → work
   continues normally.
3. **Pinned and reviewable.** Repos pin a registry version. Upgrading is a commit in a PR, visible
   as a diff, revertible like anything else. No repo's docs change because someone merged something
   somewhere else.
4. **Machine-checked, not review-nagged.** Normalization is enforced by a linter in CI against a
   schema. A convention that depends on a reviewer remembering it is not a convention.
5. **PR-based in both directions.** Pull opens a PR in the repo; push opens a PR in the registry.
   No automation writes to `main` anywhere.
6. **The repo's copy always wins.** The central catalog is a read-only mirror for search and
   reporting. It must never become a second source of truth that repos have to reconcile against.

## 3. What flows in each direction

**Registry → repo** (vendored; the repo never edits these):

- Spec template and its JSON-schema front-matter definition
- ADR template
- Issue templates (`user_story`, `bug_report`, `feature_request`)
- Shared workflow and convention docs
- **Standard specs** — org-wide specs repos consume as constraints (auth baseline, logging,
  accessibility, data retention)
- Lint rules

**Repo → registry** (published; the registry never edits these):

- **Spec index** — front matter of every local spec plus path, repo, and revision. Cheap, always on.
- **Spec bodies** — optional, opt-in per repo, for a searchable catalog.
- **Compliance status** — pinned template version, lint result.
- **Declared exceptions** — where this repo deviates from a standard spec it `extends`, and why.

That last item is the piece that makes standardization survive contact with reality. Repos will
deviate; the goal isn't to prevent it but to make it *visible and reasoned* instead of silent. An
exception with a stated rationale is data the central team needs; a silent deviation is a surprise
in an incident review.

## 4. Layout

**Central registry** (`org/spec-registry`):

```
templates/
  spec.md                    ADR.md
  issues/user_story.md       issues/bug_report.md       issues/feature_request.md
standards/
  spec.schema.json           # front-matter schema — the contract
  workflow.md                conventions.md
specs/                       # org-wide standard specs repos extend
  security/auth-baseline.md
  observability/logging.md
catalog/                     # published from repos; registry-owned, bot-written
  <org>/<repo>/index.json
  <org>/<repo>/specs/*.md    # only for repos publishing in `full` mode
tools/specctl/               # the CLI
```

Releases are tags (`v1.0.0`, `v1.1.0`). Repos pin a tag, never a branch.

**Consuming repo:**

```
docs/specs/*.md              # repo-owned
docs/specs/_standards/       # vendored, generated, never hand-edited
docs/adr/*.md                # repo-owned
.spec/config.yml             # registry remote, pinned ref, publish mode
.spec/lock.json              # pinned revision + per-file hashes
.github/workflows/spec.yml   # lint on PR, publish on merge, weekly upgrade check
```

## 5. Front matter: the enabling piece

Nothing here works without structured metadata on every spec. This is the schema the registry owns
and the linter enforces:

```yaml
---
id: pet-insights                 # stable slug, unique per repo, never renamed
title: Pet Insights
status: shipped                  # draft | active | shipped | superseded
owner: "@bradreimer"
created: 2026-03-04
updated: 2026-08-17
tracking_issue: 94
tags: [insights, ml]
template: org/spec@1.2.0         # template version this conforms to
extends:                         # standard specs this must conform to
  - org/observability/logging@2.0.0
exceptions:
  - spec: org/observability/logging@2.0.0
    requirement: FR-3            # ship structured logs to the central collector
    reason: local-first tool; no network egress by design (see ADR-001)
    approved_by: "@platform-team"
    expires: 2027-01-01
supersedes: null
superseded_by: null
---
```

`extends` + `exceptions` is what turns "we have standards" into something checkable. `expires`
forces exceptions to be revisited rather than becoming permanent by neglect.

Adopt this field set **before** building any tooling. Retrofitting metadata onto fifty existing
specs later is the expensive migration this avoids.

## 6. The tool: `specctl`

A single-file Python CLI living in the registry, run without installation:

```bash
uvx --from git+https://github.com/<org>/spec-registry@v1.0.0 specctl <command>
```

The pinned ref comes from `.spec/config.yml`, so every invocation is reproducible and the tool
upgrades in lockstep with the standards it enforces.

| Command | Behavior |
|---|---|
| `specctl init` | Seeds `.spec/config.yml`, vendors the current standards, writes the lockfile. |
| `specctl pull [--ref vX]` | Fetches the registry at a ref, rewrites the vendor directory, updates the lock. Reports what changed, which standard specs this repo `extends` moved, and any exception that expired. **Refuses if a vendored file was locally modified** (`--force` to overwrite) — the modification is a signal that something belongs upstream. |
| `specctl lint` | Validates every local spec against the pinned schema: front matter well-formed, required sections present and non-empty, `extends` targets resolvable, exceptions well-formed and unexpired, `id` unique, `superseded_by` links resolve. Exit non-zero on failure. |
| `specctl verify` | Confirms the vendor directory matches the lockfile hashes. Catches hand-edits and stale pulls. |
| `specctl push` | Builds `index.json` from local front matter (plus bodies in `full` mode) and opens/updates a PR against the registry's `catalog/<org>/<repo>/`. |
| `specctl new spec\|adr` | Scaffolds from the pinned template with front matter pre-filled. |
| `specctl status` | Pinned vs. latest registry version, specs failing lint, active exceptions, specs not updated in N months. |
| `specctl promote <spec>` | Opens a PR proposing a local spec as an org-wide standard spec. On acceptance, the local spec becomes `extends:` the new standard. |

`promote` is the normalization loop running in the useful direction: standards that came from real
work in a real repo, rather than being written speculatively by a central team and ignored.

## 7. CI wiring

In each consuming repo (`.github/workflows/spec.yml`):

- **On pull request** — `specctl lint` and `specctl verify`. A malformed spec or a hand-edited
  vendored file fails the build. This is where normalization actually happens; everything else is
  reporting.
- **On merge to the default branch** — `specctl push`, opening or updating the catalog PR.
- **Weekly, scheduled** — `specctl pull --check`; if the registry moved, open an upgrade PR with the
  changelog in the body. Each repo merges on its own schedule.

In the registry:

- Schema changes run a compatibility check against every catalogued repo's index and report how many
  specs a proposed change would break, before it merges.
- A dashboard (a generated markdown page is enough to start) showing per-repo template version, lint
  status, spec counts by status, and all active exceptions with expiry dates.

## 8. Rollout

Each phase is independently useful. Ship them in order — the ordering is the point.

**Phase 0 — local discipline, no tooling (day 1).** Use the seed prompt in
[seed-prompt.md](seed-prompt.md) on one repo. Templates, front matter, workflow docs, seeded specs.
No registry, no CLI. *Value: that repo gets better immediately.* Do this before anything central
exists — a registry with nothing good to distribute is a governance exercise.

**Phase 1 — registry + one-way pull (week 2–3).** Stand up the registry from the artifacts the
first repo produced, tag `v1.0.0`, add `specctl init`/`pull`/`verify`, onboard two or three repos.
*Value: templates stop drifting.*

**Phase 2 — lint in CI (week 4).** `specctl lint` blocking on PRs. Expect the first run to fail
everywhere; fix by relaxing the schema where it's over-strict, not by disabling the check. *Value:
normalization becomes mechanical instead of social.*

**Phase 3 — push + catalog (month 2).** Index-only publishing, catalog PRs, the generated dashboard.
*Value: the central team can finally see across repos.*

**Phase 4 — standard specs, `extends`, `promote` (month 3+).** Org-wide specs and the exception
loop. *Value: shared constraints that are actually tracked.*

**Do not build Phase 3 before Phase 2.** A catalog assembled from unlinted specs is a searchable
pile of inconsistent documents, and it discredits the whole effort at exactly the moment the most
people are looking at it.

## 9. Risks and open questions

- **Leakage through the catalog.** The catalog is as sensitive as the most sensitive repo publishing
  into it. Default every repo to `index-only` (titles, status, tags — no bodies); `full` mode is
  opt-in per repo with an explicit decision. Access-control the registry to at least the union of
  its contributors.
- **Breaking template changes.** A required new section forces a PR in every repo. Version templates
  explicitly, support N-1 for a deprecation window, and make the compatibility check in §7 a merge
  gate on the registry itself.
- **The registry becoming a bottleneck.** If landing a spec requires central review, teams route
  around it. Repos own their specs unilaterally; central owns only templates, schema, and standard
  specs. Keep it that way even when it's tempting not to.
- **Exceptions becoming permanent.** `expires` is mandatory for a reason; surface expired exceptions
  in `specctl status` and on the dashboard, and treat an expiring exception as a prompt to fix
  either the repo or the standard.
- **Monorepos.** One `.spec/config.yml` at the root with multiple `specs_dir` entries, published as
  one catalog entry per package. Worth deciding before the first monorepo onboards, not after.
- **Open: does the ADR corpus publish too?** ADRs are more repo-local than specs, but cross-repo
  visibility into architectural decisions is arguably more valuable. Start with specs only; revisit
  once the catalog has real usage.
- **Open: who owns the registry?** It needs a named owner with time for template review, or it
  decays into an unmaintained mirror of whatever the first repo happened to do.

## 10. Where to start

1. Run [seed-prompt.md](seed-prompt.md) against one repo (Part A only). One week of real use.
2. Take what survived that week — the template, the schema, the issue templates — and make it
   `v1.0.0` of the registry. Standards extracted from practice, not invented ahead of it.
3. Onboard the second repo with Part B included. The second repo is where you find out which parts
   of repo one were project-specific and which are genuinely shared.
