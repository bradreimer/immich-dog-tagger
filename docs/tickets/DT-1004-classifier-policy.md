# TICKET 04: Centralize nearest-neighbor decision policy

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
