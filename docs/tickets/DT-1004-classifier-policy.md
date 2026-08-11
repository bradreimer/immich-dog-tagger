# TICKET 04: Centralize nearest-neighbor decision policy

## Status
Completed

## Implementation notes
- Added `src/immich_dog_tagger/policy.py`: `ClassifierPolicy` (version, confident_threshold, candidate_limit) and `ClassificationDecision` (CONFIDENT/NEEDS_REVIEW/UNKNOWN), with a `DEFAULT_POLICY` singleton.
- `IdentityClassifier`, `ClassificationService`, and `ReviewQueryService` now take a `policy` and resolve their threshold/candidate-limit defaults from it instead of hardcoded `0.80`/`3` literals.
- `ReviewQueryService._review_reason` now derives "unknown"/"low-confidence" from `policy.decide()` instead of a second hardcoded threshold.
- CLI (`classify`, `active-review`) and the `/review` API route default to `DEFAULT_POLICY.confident_threshold` rather than a duplicated literal.
- Added `CropClassification.classifier_version` (persists which policy version produced an AUTO prediction) plus an additive migration in `database.py`.

## Goal
Make classification behavior explicit, deterministic, and testable.

## Steps
1. Locate all similarity/distance and threshold logic.
2. Consolidate it into one backend classifier/policy module.
3. Define confident, needs-review, and unknown states.
4. Preserve an explicit abstain/unknown path.
5. Version or persist the relevant classifier configuration with classification passes.
6. Add unit tests around boundary cases.

## Done when
The UI does not implement ML policy, and the same policy is used consistently by pipeline classification and Reclassify.
