# Project health

## Risks

- Classification quality depends on how many and how varied the reviewed examples for each
  identity are.
- Similar-looking individuals and sparse date metadata may need more contextual signals than the
  classifier currently uses.
- Pipeline status accounting (detection/classification job state) needs more validation at scale.

## Open questions

- The long-term Immich synchronization strategy beyond album membership.
- Whether reference-example curation should get its own workflow, separate from Review.

## Recommendations

- Keep recording architectural decisions as ADRs.
- Keep specs in sync with what's actually implemented.
- Add more integration tests around the review → learn → reclassify loop.
