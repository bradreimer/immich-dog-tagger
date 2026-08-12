# DT-1107: Give dog management its own page and nav item

## **ID**

DT-1107

## **Related spec**

[v1.2 Visual Style Refresh](../specs/v1.2-visual-style-refresh.md) -- amends the "no new nav
items" non-goal for this one case, on explicit request.

## **Priority**

Medium

## **Status**

Completed

## **Goal**

Move dog management out of Mission Control into its own `/dogs` page with a dedicated sidebar nav
item, instead of being one card among several on the operational dashboard.

## **Context**

`DogManagementCard` lived under `ui/src/features/mission-control/components/` and was rendered
inline on Mission Control, between System Diagnostics and Manual Operations. Managing dog
identities is a distinct concern from pipeline/job operations, and now that DT-1104 gave the app a
sidebar with room for more than four items, splitting it out is straightforward and requested
directly.

## **Implementation notes**

- Moved `DogManagementCard` to `ui/src/features/dogs/components/DogManagementCard.tsx` (new
  `dogs` feature folder, matching the existing `review`/`mission-control` convention of a
  `components/` subfolder). Its behavior (create/rename/activate/deactivate dogs) is unchanged --
  only its location and the surrounding chrome changed.
- Removed the card's own `CardHeader` (title "Dogs" + description) since the new
  `DogsPage.tsx` carries that via a page-level `<h1>`/subtitle, following the same pattern as
  every other page (Mission Control, Metrics, Job Queue) -- avoids showing "Dogs" twice in a row.
- New `ui/src/features/dogs/DogsPage.tsx`, new `/dogs` route in `App.tsx`, new "Dogs" sidebar
  entry (`IconDog`) in `Sidebar.tsx`, positioned after Review and before Job Queue.
- Removed the now-empty `mission-control/components/` directory and the `DogManagementCard`
  import/usage from `MissionControlPage.tsx`.

## **Acceptance criteria**

- `/dogs` renders dog management (create, rename, activate/deactivate) with full functional
  parity with the removed Mission Control card.
- Mission Control no longer shows dog management.
- The sidebar has a "Dogs" nav item that highlights when active, consistent with the other items.
- `npm run build` and `npm run lint` pass.

## **Testing requirements**

- Manual visual verification of the new Dogs page and sidebar entry, light and dark, in an
  isolated scratch environment.
- Manual exercise of create/rename/activate/deactivate on the new page to confirm no functional
  regression from the move.

## **Dependencies**

DT-1104 (sidebar shell).

## **Suggested commit message**

`feat(DT-1107): move dog management to its own page and sidebar tab`
