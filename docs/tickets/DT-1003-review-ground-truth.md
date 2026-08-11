# TICKET 03: Harden review-to-example persistence

## Goal
Ensure review decisions become reliable classifier examples without duplication or leakage.

## Steps
1. Trace every review path in the UI/backend.
2. Ensure accepted/corrected labels persist as authoritative ground truth.
3. Ensure the associated embedding is available and valid.
4. Upsert rather than duplicate the same logical example.
5. Keep prediction records separate from reviewed labels.
6. Add tests for correction, re-review, and duplicate submission.

## Done when
50-100 reviewed images reliably produce the expected labeled-example population and reclassification cannot overwrite those reviewed labels.
