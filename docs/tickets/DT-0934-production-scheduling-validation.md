# Tickets

## **ID**

DT-0934

## **Related spec**

v0.9.3 Production Validation & Pipeline Confidence

## **Priority**

High

## **Status**

Planned

## **Goal**

Prove that v0.9.1 scheduling works against real production work.

## **Context**

Scheduling must be trusted before v1.0. A scheduler that works only with synthetic jobs is not sufficient.

## **Implementation notes**

* Configure a temporary or controlled schedule in Mission Control.  
* Exercise a safe operation against the representative dataset or newly available test work.  
* Observe scheduler, job queue, and job history.  
* Stop/restart the application during a safe long-running operation if practical.  
* Verify no duplicate scheduled occurrence is created.  
* Remove or disable temporary schedules after validation.

## **Acceptance criteria**

* A real scheduled operation executes successfully.  
* Scheduler status is visible.  
* Job provenance identifies the schedule.  
* Restart does not duplicate the scheduled occurrence.  
* A failed scheduled operation remains observable.  
* Temporary validation schedules are cleaned up.

## **Testing requirements**

* Real scheduled-job execution.  
* Scheduler restart test.  
* Duplicate-occurrence verification.  
* Failure visibility test.

## **Dependencies**

DT-0933, v0.9.1 scheduler

## **Suggested commit message**

`test(validation): verify production scheduling`  
