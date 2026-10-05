# Pets per Library: Dog and Cat Breakdown on the Metrics Tab

## Purpose

With more than one Immich account/library configured
([multi-immich-account-sync.md](multi-immich-account-sync.md)), every Metrics figure is a
library-wide total. Nothing shows how many dogs and cats each library contributes, so an owner
cannot tell which library holds most of their pets or whether one library is being detected and
identified less thoroughly than another.

## User story

As an owner with several Immich libraries, I want to see how many dogs and cats each library
contains, so I can see where my pets are photographed and which library still has unidentified ones.

## Goals

- A "Pets per Library" card on the Metrics tab: one stacked bar per library, split into dogs and
  cats.
- Two stated counts per library and species, each with an explicit scope:
  - **Detected**: pet crops found in that library's photos, excluding crops a reviewer flagged as
    not an animal.
  - **Identified**: those crops that have a settled identity (a `PetOccurrence`).
- Species comes from `Crop.species`, the reviewer-correctable value, not the detector's raw label.
- Read-time derived: no new tables, columns, or stored conclusions.
- Fixed number of aggregate queries regardless of library size (no per-library or per-row loop).

## Non-goals

- Per-library classification quality (confident, needs-review, unknown) or review-queue counts.
- Making the chart filter the rest of the Metrics page.
- Counting photos instead of crops. A photo with two dogs counts as two detected dogs.
- Species other than dog and cat.

## Requirements

- `MetricsService.pets_per_library()` returns one entry per library that has at least one
  detected pet, ordered by total detected pets (descending), then library name.
- Each entry holds the library name plus detected and identified counts for dogs and for cats.
- Crops whose photo has no account are grouped under a library named "Unassigned".
- Crops with `not_animal` set are excluded from both counts.
- `GET /api/metrics/pets-per-library` returns the entries. The route goes through the service.
- The Metrics page shows the card only when two or more libraries have detected pets. With one
  library, the card is hidden, since the totals already on the page are that library's numbers.
- Each bar is accessible: its label states the library, dog count, and cat count. Dogs and cats
  use distinct chart palette colors, with a legend.

## Acceptance criteria

- Given two libraries with 3 dogs + 1 cat and 1 dog + 2 cats, the endpoint returns both, each with
  the right per-species detected counts.
- Given a crop with a settled identity, the identified count for its library and species includes
  it; a crop with no identity is detected but not identified.
- Given a crop flagged `not_animal`, neither count includes it.
- Given a crop whose species a reviewer corrected from dog to cat, it counts as a cat.
- Given a photo with no account, its crops appear under "Unassigned".
- Given one library only, the Metrics page does not render the card.
- Given two or more libraries, the card renders one bar per library with a dog and cat segment
  and a legend.

## Open questions

- None. A photo-denominated variant (like Detection Coverage) can follow if crop counts prove
  confusing.
