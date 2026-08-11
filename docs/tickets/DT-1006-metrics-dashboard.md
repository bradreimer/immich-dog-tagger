# TICKET 06: Metrics and dashboard

## Goal
Show users whether manual review is becoming less necessary.

## Steps
1. Define persisted queries for eligible, reviewed, labeled-example, confident, review, and unknown counts.
2. Add recommendation coverage and review rate.
3. Add last reclassification and pass history.
4. Track prediction changes between passes.
5. Add a compact trend graph over passes/batches.
6. Make denominators explicit in labels/tooltips.
7. Do not show precision/accuracy unless a valid held-out evaluation set exists.

## Done when
The main page gives a trustworthy snapshot of project learning progress and the values match database state.
