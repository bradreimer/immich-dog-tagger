# TICKET 08: 30,000-image scale validation

## Goal
Validate that v1.0 can operate on a large archive without browser or server resource blowups.

## Steps
1. Build a representative load-test dataset or fixture.
2. Measure memory and runtime for scan, embedding reuse, and reclassification.
3. Verify batching and pagination.
4. Find and fix obvious N+1 database access.
5. Ensure the browser never receives the full archive in one payload.
6. Establish documented operational expectations for a 30,000-image project.

## Done when
A representative 30,000-image workload completes or can be processed in bounded batches with documented resource behavior.
