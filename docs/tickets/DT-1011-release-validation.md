# DT-1011: v1.0.0 release validation

## **ID**

DT-1011

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- section 7 (Acceptance criteria), section 8 (Non-goals)

## **Priority**

High

## **Status**

Pending

## **Goal**

Verify the complete release against the specification.

## **Context**

DT-1000 through DT-1010 implement and document every v1.0.0 requirement individually. This ticket is the release gate: verify the assembled whole against the spec's acceptance criteria, close any release-blocking defects found, and tag the release only once everything passes.

## **Steps**

1. Run all automated tests.
2. Perform a fresh-install test.
3. Process a representative project.
4. Complete an initial manual review batch.
5. Reclassify from the web UI.
6. Verify metrics.
7. Verify restart/recovery behavior.
8. Run scale validation.
9. Review logs for sensitive-data leakage.
10. Update changelog/release notes.
11. Tag v1.0.0 only after all acceptance criteria pass.

## **Acceptance criteria**

Every v1.0.0 acceptance criterion (spec section 7) is demonstrated and no release-blocking defects remain.

## **Testing requirements**

Full `./scripts/check.sh`, plus the manual verification steps above.

## **Dependencies**

DT-1000 through DT-1010.

## **Suggested commit message**

`docs(release): v1.0.0 release validation`
