# Tickets

## **ID**

DT-0931

## **Related spec**

v0.9.3 Production Validation & Pipeline Confidence

## **Priority**

High

## **Status**

Planned

## **Goal**

Define and process a bounded production validation dataset representative of the real Immich library.

## **Context**

A full-library run is too large to be the first validation step. We need a small, known dataset that exercises the important behaviors before committing to a long production run.

## **Implementation notes**

* Select a representative set from the real Immich library on `schnorbit`.  
* Include known identities, unknowns, multiple dogs, conflicts, low confidence, different years, imperfect metadata, and already-processed assets.  
* Preserve a record of the selected assets so the validation can be repeated.  
* Do not alter or delete the source Immich assets.  
* Use existing scan/detection/classification infrastructure.

## **Acceptance criteria**

* A bounded representative dataset exists.  
* The dataset exercises all required review reasons.  
* Assets span relevant temporal metadata cases.  
* The validation dataset can be reproduced.  
* No source Immich data is modified destructively.

## **Testing requirements**

* Validate asset selection.  
* Run scan against the dataset.  
* Confirm expected assets enter `state.db`.  
* Record baseline counts and observations.

## **Dependencies**

v0.9.2 complete

## **Suggested commit message**

`test(validation): define representative production dataset`  
