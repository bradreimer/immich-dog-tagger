# Task: establish spec-driven, ticket-driven development in this repository

You are setting up a lightweight development discipline for this codebase. **Do not write or
change product code.** Your output is documentation, templates, and process scaffolding that make
future changes flow through: *idea → spec → ticket → implementation → tests → docs → commit*.

The goal is a repo where an agent or a new contributor can read a handful of files and know what
this project is, what it's trying to do, what shape a change proposal takes, and what "done" means
— without asking anyone.

## Step 1 — Investigate before writing anything

Read the repository first. Do not generate a single file until you can answer these from evidence:

- What does this project actually do, in two sentences, for whom?
- What are the primary languages, frameworks, and the real architectural layers/boundaries?
- What are the **exact** commands to install, build, test, lint, and format? Get them from
  `package.json` / `pyproject.toml` / `Makefile` / CI workflows — never guess or use a plausible
  default.
- What documentation already exists (`README`, `CONTRIBUTING`, `docs/`, `CLAUDE.md`, ADRs, wikis)?
  What is already accurate, and what is stale?
- Is the project using GitHub Issues (or Jira/Linear/other)? Do issue or PR templates already
  exist? Are there labels in use?
- What CI runs on a pull request?
- Read the last ~30 commits: what do commit messages look like, how large is a typical change,
  is there an existing convention (`feat(scope):`, plain sentences, ticket prefixes)?
- What are the 2–4 load-bearing design decisions already baked into this codebase — the ones a
  newcomer would otherwise violate? (e.g. "X is the source of truth", "layer A never calls B
  directly", "this stays offline-only".)

Then post a short findings summary and **stop for my confirmation** if any of these are true:
the project's purpose is ambiguous, there's an existing workflow doc that conflicts with what
you're about to add, or the issue tracker isn't GitHub Issues. Otherwise continue straight into
Step 2 and tell me what you're assuming.

Ask me at most three questions total, and only ones whose answers change what you write.

## Step 2 — Create the scaffolding

Create each of the following. Adapt names/paths to this repo's existing conventions if it already
has some — do not create a parallel second structure.

### 2.1 `docs/specs/README.md`

Explains what a spec is here, when one is required, and the template. Requirements:

- **When a spec is required**: user-facing behavior changes, workflow design, cross-cutting
  architecture. **When it isn't**: bug fixes that restore documented behavior, refactors with no
  behavior change, dependency bumps, docs/test-only changes. State both — a rule with no exclusions
  gets ignored wholesale.
- **Spec lifecycle**: `draft → active → shipped → superseded`. A spec is a living record of intent,
  not a one-time gate. When a later spec replaces an earlier one, the old one gets
  `status: superseded` and a link forward rather than being deleted.
- **The template**, exactly these sections:
  - **Purpose** — what problem, why now. Include what exists today and why it's insufficient.
  - **User story** — `As a <user>, I want <capability>, so that <benefit>.`
  - **Goals** — what this iteration delivers.
  - **Non-goals** — what it deliberately does *not* do, **with the reason**. This is the highest-value
    section in the whole template: it's what stops scope creep and what a future reader needs most.
  - **Requirements** — the substance. Concrete enough to implement from: names, shapes, endpoints,
    states, error behavior.
  - **Acceptance criteria** — observable, checkable outcomes, ideally Given/When/Then.
  - **Open questions** — unresolved points, each with a note on why it's safe to defer.
- **Front matter**: every spec starts with the YAML block in §2.7 below. State that it's mandatory.
- A worked note on quality: a good spec is specific enough that two different implementers would
  build compatible things, and it says what it won't do. A spec that only lists features is a
  backlog, not a spec.

Also create `docs/specs/_template.md`: the front matter plus the section headings with a one-line
HTML comment prompt under each, ready to copy.

### 2.2 `docs/adr/README.md` + `docs/adr/ADR-001-<slug>.md`

ADRs record decisions that constrain future work. Sections: **Status**, **Context**, **Decision**,
**Alternatives considered**, **Consequences** (including the negative ones — an ADR with no
downsides listed is marketing, not a record).

Write **ADR-001 for the single most load-bearing decision already made in this codebase**, from
your Step 1 findings. Not a hypothetical future decision — the real one that's already true, that
someone could accidentally undo. Reference the actual files/modules where it's enforced.

### 2.3 Issue templates in `.github/ISSUE_TEMPLATE/`

Three templates. The distinction between them matters more than their contents:

- `user_story.md` — a **scoped, implementation-ready** capability. Fields: Related spec, Priority,
  Story (As a/I want/So that), Context, Implementation notes, Acceptance criteria, Out of scope,
  Testing requirements, Dependencies, Suggested commit message. Labels: `user-story`.
- `bug_report.md` — a defect. Fields: Related spec, Priority, Description, Steps to reproduce,
  Expected behavior, Actual behavior, Environment, Root cause / implementation notes, Acceptance
  criteria, Testing requirements, Dependencies, Suggested commit message. Labels: `bug`.
- `feature_request.md` — an **unscoped idea**, explicitly the input to a spec rather than something
  to implement directly. Fields: Problem, Proposed solution, Alternatives considered, Related spec,
  Priority, Additional context. Labels: `enhancement`. End it with a note that it must be refined
  into a spec and a User Story before implementation.

The "Suggested commit message" and "Related spec" fields on the first two are what wire the three
layers (spec → ticket → commit) together. Keep them.

If this project uses a tracker other than GitHub Issues, produce the equivalent for that tracker
instead and say so.

### 2.4 `docs/development-workflow.md`

The short operational loop, one screen long. The flow line, what to check before starting work,
commit conventions **with real examples from this repo's actual scopes/modules**, the exact
validation commands from Step 1, and what a release requires. This file is read often — keep it
scannable. Depth belongs in `CONTRIBUTING.md`, not here.

### 2.5 `docs/status.md` and `docs/roadmap.md`

- `status.md`: **Completed** (real, from git history and the actual state of the code — no
  invented milestones), **Current milestone**, **Next work**, **Known issues / gaps** (be honest:
  missing auth, untested paths, known scale limits). This is the file that answers "where are we?"
  and it must be true on the day you write it.
- `roadmap.md`: milestone-level direction — Goal, Features, Exit criteria per milestone. Only
  include future milestones you can justify from the repo's own TODOs, issues, and gaps. If you
  can't justify any, write the current one and say the rest is undecided. **An invented roadmap is
  worse than no roadmap.**

### 2.6 `CLAUDE.md` (create or amend) and `CONTRIBUTING.md`

`CLAUDE.md` is the agent's entry point and must be dense and skimmable, not exhaustive. Include:

1. What this project is (2–4 sentences) and its **core principle** — the one invariant that, if
   violated, breaks everything. Link the ADR.
2. The spec-driven/ticket-driven workflow as a numbered list, stated as *required*, with links.
3. Architecture — the real layers and what each owns, with file/directory paths.
4. Working conventions — the judgment calls: what to prefer, what's irreversible and needs care,
   what must never happen (privacy, security, data-loss boundaries), commit-message shape.
5. **Validation before considering work done** — exact commands, copy-pasteable.
6. A key-docs map.

Rules for this file: every path and command in it must exist and work. Prefer linking to a doc over
restating it. If `CLAUDE.md` already exists, amend it in place — don't duplicate sections.

In `CONTRIBUTING.md`, add (or extend) an **Architecture principles** section explaining the *why*
behind the decisions in `CLAUDE.md`, plus sections on what makes a good change, testing
expectations, and any data/privacy/security boundary specific to this project.

### 2.7 Spec front matter (required in every spec)

```yaml
---
id: <stable-kebab-slug>          # unique within this repo, never renamed
title: <human title>
status: draft                    # draft | active | shipped | superseded
owner: <@github-handle or team>
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
tracking_issue: <number or null>
tags: [<domain>, <area>]
template: org/spec@1.0.0         # template version this conforms to
extends: []                      # org-wide specs this must conform to
exceptions: []                   # declared deviations from an extended spec, each with a reason
supersedes: null
superseded_by: null
---
```

Include this even if there is no central registry yet — it costs nothing now and is what makes
cross-repo indexing, linting, and sync possible later without a migration.

## Step 3 — Seed real content, not placeholders

Templates alone don't create a practice; the first real examples do. Produce:

- **One to three specs describing behavior that already exists**, written by reading the code —
  pick the areas most central to the product. `status: shipped`. These are the reference examples
  everyone copies, so make them genuinely good: real module names, real endpoints, real edge cases,
  and honest Non-goals. Do not backfill a spec for every existing feature — that's archaeology, and
  it produces documentation nobody trusts.
- **ADR-001** as described above.
- Optionally **one `draft` spec** for a real gap you found (something in `status.md`'s known
  issues), to demonstrate the forward-looking shape.

## Step 4 — Rules while doing this

- **Proportional.** This is process scaffolding for a working codebase, not a compliance regime.
  If the repo is a 500-line CLI, the whole setup is smaller. Match the ceremony to the stakes.
- **Never invent history.** No fabricated milestones, dates, decisions, contributors, or completed
  work. Everything traceable to code, git history, or issues.
- **Never open issues for work that's already done**, and don't bulk-create issues at all unless I
  ask. Create at most one or two to demonstrate the template, and ask before creating any.
- **Exact commands only.** Every command you write must be one you found in the repo, and ideally
  one you ran.
- **No placeholder prose.** No "TODO: describe the architecture", no lorem ipsum, no
  `<your project here>`. If you genuinely can't determine something, write the question into
  `status.md`'s open items and tell me.
- **Don't restructure existing docs** beyond what's needed to avoid contradiction. If an existing
  doc conflicts with the new workflow, flag it rather than silently rewriting it.
- Preserve this repo's existing voice and formatting conventions (line width, heading style,
  American/British spelling, whether it uses emoji).

## Step 5 — Validate and commit

- Verify every internal link resolves and every referenced path exists.
- Run the repo's own doc/lint checks if any apply (markdown lint, link checkers, spell check).
- Commit in small, logical commits, using the commit convention you found in Step 1:
  1. spec framework (specs README + template)
  2. ADR framework + ADR-001
  3. issue templates
  4. workflow, status, roadmap docs
  5. CLAUDE.md / CONTRIBUTING.md updates
  6. seeded specs
- Do **not** open a pull request unless I ask.

## Definition of done

- [ ] A new contributor can read `CLAUDE.md` and know what to do before writing code.
- [ ] `docs/specs/README.md` states when a spec is required *and when it isn't*.
- [ ] At least one seeded spec is good enough to be the model everyone else copies.
- [ ] ADR-001 records a decision that is actually already true in this codebase.
- [ ] Three issue templates exist, and the difference between them is clear from reading them.
- [ ] Every command in every doc is real and was run.
- [ ] Every spec carries the front matter block from §2.7.
- [ ] `status.md` is an accurate description of the repo today.
- [ ] Nothing in the docs is invented.

---

# Part B (optional) — prepare for a central spec registry

Include this part only if the team runs a shared spec repository. Delete it otherwise; everything
above stands alone, and Part B can be added later without reworking anything.

Additionally create:

### `.spec/config.yml`

```yaml
version: 1
registry:
  remote: <git URL of the central spec repository>
  ref: v1.0.0                 # pinned tag; upgrades are explicit commits
  channel: stable
local:
  specs_dir: docs/specs
  adr_dir: docs/adr
  vendor_dir: docs/specs/_standards   # generated; never hand-edited
publish:
  mode: index-only            # index-only | full   (index-only ships metadata, not spec bodies)
  catalog_path: catalog/<org>/<repo>
```

### `.spec/lock.json`

Records the pinned registry revision and a hash per vendored file, so CI can prove the vendored
copy matches upstream and hasn't been locally edited.

### `docs/specs/_standards/README.md`

A stub stating that everything in this directory is vendored from the central registry, is
regenerated by `specctl pull`, and must never be edited by hand — local changes belong upstream.

### A `## Spec registry` section in `CLAUDE.md`

Stating the one-owner-per-file rule: **this repo owns `docs/specs/*.md` and `docs/adr/*.md`; the
registry owns everything under the vendor directory and the issue templates.** Neither side edits
the other's files, so sync is a copy, never a merge.

Do not build sync tooling as part of this task — just leave the repo in a state where
`specctl pull` works on day one.
