# Spec workflow kit

Portable versions of this project's spec-driven, ticket-driven development patterns, for use in
other repositories.

- **[seed-prompt.md](seed-prompt.md)** — a prompt to paste into an agent working in another
  codebase. It investigates the repo, then produces the spec framework, ADR framework, issue
  templates, workflow/status/roadmap docs, `CLAUDE.md`/`CONTRIBUTING.md` sections, and one to three
  seeded specs written from that repo's real code. Part A stands alone; Part B adds the scaffolding
  for central sync.
- **[central-spec-registry-plan.md](central-spec-registry-plan.md)** — a plan for keeping specs
  local to each repo while a central team normalizes their shape and publishes shared standards,
  with push/pull between repos and a central registry.

These describe the patterns documented in [../development-workflow.md](../development-workflow.md),
[../specs/README.md](../specs/README.md), and [../adr/README.md](../adr/README.md) — generalized so
they can be applied elsewhere. Nothing here affects this project's own build or runtime.

If the registry in the plan gets built, this directory is the natural thing to move into it: the
seed prompt belongs next to the templates it generates.
