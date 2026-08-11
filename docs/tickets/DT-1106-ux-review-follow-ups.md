# DT-1106: UX review follow-ups from the visual style refresh

## **ID**

DT-1106

## **Related spec**

[v1.2 Visual Style Refresh](../specs/v1.2-visual-style-refresh.md)

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Re-compare the DT-1104/DT-1105 implementation against the reference mockup and each page's own
usability, and fix what's actually worth fixing -- without re-opening the scope decisions already
made in v1.2 (no new nav items, no new backend fields, no fabricated data/links).

## **Context**

After DT-1105 landed, a side-by-side review against the reference mockup and a fresh look at each
tab surfaced four findings. Two are drawn from the mockup (relative timestamps, a bottom
next-action nudge, an automation trend delta); one is a pre-existing bug this review happened to
surface (not something DT-1104/DT-1105 introduced, but appeared in a `Deactivate dog` screenshot
taken during verification).

Explicitly **not** revisited here, because DT-1104/1105 already decided them deliberately: adding
Dogs/Albums/Settings nav items, a per-dog coverage chart, a predictions-changed breakdown donut,
an average-similarity chart, a dual-axis chart, replacing the sidebar's photographic logo with a
vector mark (no such asset exists to substitute), or adding Docs/GitHub links/a version string to
the sidebar footer (no confirmed public URL or wired-up version source exists to show -- inventing
one would violate the project's "don't fabricate" rule, not improve the UX).

## **Implementation notes**

- **Fixed `destructive` button variant** (`ui/src/components/ui/button-variants.ts`): it was
  byte-for-byte identical to `default` (`border-primary bg-primary text-primary-foreground...`),
  so `DogManagementCard`'s "Deactivate" button rendered in the same blue as "Run Pipeline" --
  indistinguishable from a primary action, violating ux-principles.md principle 8 ("destructive
  actions... use the established destructive-action styling"). Now uses the existing
  `--destructive` token; added the missing `--destructive-foreground` token (white) it needed for
  readable text, in both light and dark theme.
- **Relative "last updated" timestamp** on Mission Control: replaced the raw `HH:MM:SS` string
  with a short relative format ("just now", "5m ago", "2h ago"), matching the mockup's "Last
  updated: 2 min ago" and easier to scan at a glance than an absolute clock time.
- **Contextual next-action banner** on Mission Control, matching the mockup's bottom tip card:
  when the review queue is non-empty, a banner points at Review with the pending count; when
  empty, a quieter "all caught up" message. Built from `ReviewQueueStats`, already fetched by the
  page -- no new data source.
- **Automation trend delta** on the Metrics automation card, matching the mockup's "Review
  Reduction Trend" callout: when at least two recorded passes have a non-null
  `review_queue_size`, shows how many percentage points the no-review-needed share moved between
  the first and most recent such pass. Computed client-side from `pass_history`, which already
  carries everything needed -- no backend change.

## **Acceptance criteria**

- The `destructive` button variant is visually distinct from `default` in both themes and passes
  a quick contrast check.
- Mission Control shows a relative "last updated" time and a next-action banner reflecting the
  live review-queue count.
- The Metrics automation card shows a trend delta only when the underlying data supports it
  (>= 2 passes with recorded `review_queue_size`); otherwise it is omitted, not fabricated.
- `npm run build` and `npm run lint` pass.

## **Testing requirements**

- Manual visual verification of the destructive button, the banner (both empty and non-empty
  queue states), and the trend delta (with and without enough pass history) in an isolated
  scratch environment, light and dark.

## **Dependencies**

DT-1104, DT-1105.

## **Suggested commit message**

`fix(DT-1106): destructive button contrast, relative timestamp, next-action banner, trend delta`
