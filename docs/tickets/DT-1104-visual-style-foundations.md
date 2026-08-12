# DT-1104: Visual style foundations -- design tokens, sidebar shell, shared primitives

## **ID**

DT-1104

## **Related spec**

[v1.2 Visual Style Refresh](../specs/v1.2-visual-style-refresh.md) -- FR-1, FR-2, FR-3, FR-4

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Land the reusable pieces the rest of the visual refresh depends on: the blue accent token, a
validated status/categorical color palette, a fixed dark sidebar navigation shell, and a
reusable stat-tile component -- so every page-level ticket consumes the same primitives instead
of re-deriving colors and layout per page.

## **Context**

The current UI uses a horizontal pill nav (`Header.tsx`), an amber/orange `--primary` token, and
per-page ad-hoc `rgba(251,191,36,...)` gradient cards. `docs/specs/v1.2-visual-style-refresh.md`
defines the target: a dark sidebar shell, a blue primary accent, and status colors
(good/warning/serious/critical) used consistently for the same concept everywhere. This ticket is
the foundation layer; DT-1105 applies it to each page.

## **Implementation notes**

- `ui/src/index.css`: replaced the amber-hued `--primary`/`--ring`/`--sidebar-primary` oklch
  values with the `dataviz` skill's validated categorical slot 1 blue (`#2a78d6` light /
  `#3987e5` dark), in both `:root` and `.dark`. Added status-role custom properties
  (`--status-good`, `--status-warning`, `--status-serious`, `--status-critical`) and a small
  categorical set for non-status chart series, using the same skill's validated hex values
  (verified with `validate_palette.js`, not eyeballed).
  Fixed the previously-unused `--sidebar*` tokens to the same dark-navy values in both `:root`
  and `.dark`, so the sidebar chrome does not change with the content theme toggle.
- New `ui/src/components/layout/Sidebar.tsx` replacing `Header.tsx`'s nav: fixed-width vertical
  sidebar, one entry per existing route with a Tabler icon, active-route highlight (background
  only, no hover animation, consistent with ux-principles.md's non-action-surface rule), the
  Review nav badge (reads `ReviewQueueStats.remaining`, already fetched today), and the theme
  toggle moved into the sidebar footer. `AppShell.tsx` updated to a flex layout (sidebar + main
  content); collapses to a compact/icon rail below a width breakpoint rather than disappearing.
- New `ui/src/components/ui/stat-tile.tsx`: icon-in-colored-circle + label + value + subtext +
  optional progress bar, taking a `tone` prop (`good`/`warning`/`serious`/`critical`/`info`)
  mapped to the new status tokens.
- `buttonVariants`/`badgeVariants` required no changes -- both already derive from `--primary`,
  so the accent swap is a token-only change, confirmed by inspection.

## **Acceptance criteria**

- `--primary` (and everywhere it flows: buttons, focus rings, active-nav state) renders the new
  blue in both themes.
- Status colors are defined once as tokens and used by name (`good`/`warning`/`serious`/
  `critical`), not re-hardcoded per component.
- The sidebar renders identically (dark) regardless of the light/dark content theme.
- `StatTile` and `Sidebar` have no page-specific logic -- they take data via props only, so
  DT-1105 can consume them from every page without modification.

## **Testing requirements**

- `npm run build` and `npm run lint` pass.
- Manual visual verification of the sidebar (active state, badge, theme toggle, collapsed/narrow
  width) and a sample `StatTile` render, light and dark, in an isolated scratch environment.

## **Dependencies**

None (foundation ticket; DT-1105 depends on this).

## **Suggested commit message**

`feat(DT-1104): blue accent tokens, sidebar shell, and stat-tile primitive`
