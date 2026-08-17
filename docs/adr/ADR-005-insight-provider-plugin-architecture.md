# ADR-005: Insight Provider Plugin Architecture

## Status
Accepted

## Context
[ADR-004](ADR-004-pet-occurrence-observations.md) decided that every fun insight (favourite human,
favourite place, and similar) is computed fresh at read time from `PetOccurrence`/`Asset` facts,
never stored as a conclusion. Its Consequences section predicted that "adding a new insight ... is
a new read-time query over existing facts, not a new column or migration" — but it didn't say
*where that query lives*. In practice, every insight so far (`summary`, `timeline`, `places`,
`people`) is a bespoke method inline in `InsightsService`, each with its own aggregation logic and,
for `summary`, its own typed response field.

v1.6.0's spec deliberately deferred a second wave of insights of the same shape: Milestones, On
This Day, Best Friends, and a Pet World Tour map ([docs/specs/v1.6-pet-insights.md](../specs/v1.6-pet-insights.md)
Non-goals). Landing each one the same way `summary()`'s existing fields were built means growing one
already-multi-purpose service method, and usually a new typed endpoint, per insight — with no
isolation between them: a bug in a new Milestones calculation risks the same method that computes
today's favourite-place/favourite-human counts.

[docs/specs/v1.7-pluginable-insights.md](../specs/v1.7-pluginable-insights.md) asks a narrower
question than ADR-004 did: not *whether* to store conclusions (settled — never), but how to keep
adding new read-time computations without every addition touching shared code.

## Decision
Introduce a single-purpose `InsightProvider` interface and an explicit, in-process registry:

- `InsightProvider` is a `Protocol` (matching the existing `Embedder` interface in `embedder.py`
  and `Clock` in `services/scheduler.py` — this codebase's established pattern for a small
  structural interface, not a new convention). One provider computes one fact, given an
  `InsightContext` (the identity, its own `PetOccurrence` rows joined to `Asset`, a `Session` for
  the rare cross-identity query, and an injected clock for time-relative insights like On This Day).
  It returns one `InsightCard` or `None` — `None` means "not enough data yet," never a fabricated
  placeholder, continuing ADR-004's rule.
- Providers are registered in one explicit Python list (`INSIGHT_PROVIDERS` in
  `services/insights/providers/__init__.py`), not discovered dynamically. Adding an insight means
  adding one file implementing the protocol and one line in that list.
- The three existing single-fact insights that were opinionated aggregations inline in
  `InsightsService.summary()` (favourite place, favourite human, Immich-favorite count) are
  refactored onto this same mechanism, so there is exactly one system determining every fun
  insight — not a legacy path for the original four and a new path for everything after. This is a
  behavior-preserving refactor: `InsightsService.summary()`'s method signature and response shape
  are unchanged.
- A new generic endpoint (`GET /api/dogs/{id}/insights/cards`) surfaces whatever's currently
  registered, so the UI renders new providers automatically instead of needing a new endpoint and a
  new UI element per insight. `timeline`/`places`/`people` are unaffected — they return ranked
  collections, not single facts, and don't fit this shape.

## Alternatives Considered
- **Keep adding bespoke methods to `InsightsService`, one per insight** (the status quo). Rejected:
  this is exactly the growth pattern the spec is trying to stop — every new insight touches shared
  code and a shared file, with no isolation, and each needs its own typed endpoint and UI wiring
  before it can ship.
- **Dynamic/third-party plugin loading** (Python `entry_points`, loading arbitrary installed
  packages, a plugin marketplace). Rejected: this is a local-first, single-operator tool with one
  deployment, not a platform with external plugin authors. That kind of loading adds real
  complexity (discovery, versioning, trust boundary for arbitrary code) for a need that doesn't
  exist here — CONTRIBUTING's "the goal isn't an elaborate ML platform" applies directly.
  "Pluginable" in the spec means easy to extend *within* this codebase, not installable from
  outside it.
- **A decorator-based self-registration mechanism** (`@register_insight_provider`, populating a
  module-level list as a side effect of import). Considered for the light discoverability win, but
  rejected in favor of the explicit list: this codebase has no existing precedent for
  import-time-side-effect registration, an explicit list is equally low-effort to add to, and it
  keeps "what's registered" visible in one place without needing to trace which modules get
  imported.
- **Force every existing insight (`timeline`, `places`, `people`) into the same
  one-provider-one-card shape**, for full uniformity. Rejected: those return ranked collections, not
  a single fact — reshaping them into cards would either lose the ranking (only show the top item)
  or require the protocol to support list-valued results, weakening the "one provider, one fact"
  simplicity that makes new insights easy to write and reason about. They stay as dedicated
  endpoints.

## Consequences
Landing a new insight (On This Day, Best Friends, further Milestones) after this lands is: write
one class implementing `InsightProvider`, add one line to `INSIGHT_PROVIDERS`, add one test. No
change to `InsightsService`'s existing methods, no new endpoint, no frontend change beyond the
one-time card-grid section this spec adds. The cost is one more explicit interface and registry in
a codebase that has favored ad hoc methods so far — justified here because insights are, by
ADR-004's own design, an open-ended, additive category (the deferred list already names four more),
unlike most of this codebase's other services, which have a fixed, closed set of responsibilities.
A `LIBRARY`-scope provider (Best Friends) still does its own real aggregation query per request,
same as `places()`/`people()` already do — this ADR doesn't change the "no precomputed cache"
decision from ADR-004, only how the query is organized in code.
