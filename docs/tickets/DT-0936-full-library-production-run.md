# Tickets

## **ID**

DT-0936

## **Related spec**

v0.9.3 Production Validation & Pipeline Confidence

## **Priority**

High

## **Status**

Planned

## **Goal**

Process the real Immich library incrementally using the production architecture.

## **Context**

The system must demonstrate that the pipeline works at the scale for which it was built, not merely on a curated sample.

## **Implementation notes**

* Take a fresh v0.9.2 backup before beginning.  
* Confirm diagnostics and job visibility are functioning.  
* Process the library incrementally.  
* Monitor database/derived-data growth and obvious resource problems.  
* Do not change multiple architectural variables during the run.  
* Record major timings, counts, failures, and retries.  
* If a defect occurs, stop only when continuing could compromise authoritative state.

## **Acceptance criteria**

* The full library is processed incrementally, or a production-scale run is completed with documented limitations.  
* Job history remains coherent.  
* No duplicate authoritative records are introduced.  
* Failures are identifiable.  
* Resource behavior is acceptable for unattended operation.  
* Backup remains available before and after the run.

## **Testing requirements**

* Production-scale run.  
* Incremental/repeat validation.  
* Job-count and database-count verification.  
* Backup verification.  
* Operational observation log.

## **Dependencies**

DT-0932, DT-0935

## **Suggested commit message**

`test(validation): complete production-scale library run`  
