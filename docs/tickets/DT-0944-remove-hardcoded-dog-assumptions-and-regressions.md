# Tickets

## **ID**

DT-0944

## **Related spec**

v0.9.4 Dynamic Dog Management

## **Priority**

High

## **Status**

Planned

## **Goal**

Remove remaining hard-coded dog-name assumptions and lock the dynamic behavior in with regression coverage.

## **Context**

The backend and UI can only be considered complete once all static dog-name references are removed from product surfaces and tests cover the new behavior.

## **Implementation notes**

* Replace static identity lists with data-driven sources.
* Update learning, review, and classification flows to read the managed dog list.
* Remove stale hard-coded dog names from the UI and documentation where they are implementation details.
* Add regression tests for the empty-install and dynamic-identity flow.
* Verify no path still assumes Fibs/Hermann/Henri exist by default.

## **Acceptance criteria**

* No user-facing hard-coded dog list remains.
* The system behaves correctly when no dogs exist.
* Existing learning and review flows still work with managed dogs.
* Regression tests prove the dynamic path.
* `./scripts/check.sh` passes.

## **Testing requirements**

* End-to-end dynamic-dog regression test.
* Empty-state review/UI test.
* CLI/API regression coverage where applicable.
* Full project validation.

## **Dependencies**

DT-0941, DT-0942, DT-0943

## **Suggested commit message**

`test(dogs): remove hard-coded dog assumptions`
