# Tickets

## **ID**

DT-0935

## **Related spec**

v0.9.3 Production Validation & Pipeline Confidence

## **Priority**

High

## **Status**

Planned

## **Goal**

Validate that Dog Tagger can safely synchronize authoritative state into Immich.

## **Context**

Sync is an external side effect and therefore needs explicit production validation before v1.0.

## **Implementation notes**

* Start with the safest available dry-run/preview behavior.  
* Record expected album changes.  
* Apply synchronization to a controlled subset.  
* Verify results directly in Immich.  
* Repeat synchronization to test idempotency.  
* Verify no unintended deletion or removal occurs.  
* Exercise failure reporting where safely possible.

## **Acceptance criteria**

* Expected albums are created or updated.  
* Expected assets appear in the intended organization.  
* Repeated sync is idempotent.  
* No unintended assets are removed.  
* Sync failures are visible through job history/diagnostics.  
* `state.db` remains authoritative.

## **Testing requirements**

* Dry-run validation.  
* Controlled real sync.  
* Repeat-sync validation.  
* Failure-path validation where safe.  
* Immich result verification.

## **Dependencies**

DT-0933

## **Suggested commit message**

`test(validation): verify safe immich synchronization`  
