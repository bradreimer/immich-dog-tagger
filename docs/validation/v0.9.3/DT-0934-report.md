# DT-0934 Validation Report

## Summary

Production scheduling was validated with temporary real schedules against production state. Validation covered:

- successful scheduled execution,
- duplicate-occurrence prevention across a restart-like second dispatch,
- failed scheduled operation visibility,
- cleanup of temporary schedules.

## Validation Execution

A scheduler validation script created two temporary schedules with expression matching the current UTC minute:

- `v0934-validation-scan-...` (operation `SCAN`) for successful run
- `v0934-validation-learn-fail-...` (operation `LEARN`) for controlled failure visibility

The script then:

1. Dispatched due schedules in one session.
2. Reopened a new session and dispatched again (restart simulation).
3. Verified no duplicate scheduled job for the successful schedule.
4. Verified failed schedule job status and error message.
5. Disabled both temporary schedules.

## Observed Output

```text
scheduled_scan_first_dispatch_jobs=[11]
scheduled_scan_second_dispatch_jobs=[]
scheduled_learn_failure_status=failed
scheduled_learn_failure_error=reference directory not found
```

Persisted DB evidence:

```text
pipeline_schedules:
1|v0934-validation-scan-...|SCAN|0
2|v0934-validation-learn-fail-...|LEARN|0

pipeline_jobs:
11|SCAN|COMPLETED|schedule_id=1
12|LEARN|FAILED|schedule_id=2|reference directory not found
```

## Acceptance Mapping

- Real scheduled operation executed successfully: yes (`SCAN`, job 11).
- Scheduler status/provenance visible: yes (`schedule_id` links in `pipeline_jobs`).
- Restart did not duplicate occurrence: yes (second dispatch produced no extra scan job).
- Failed scheduled operation observable: yes (`LEARN` failure with persisted error message).
- Temporary schedules cleaned up: yes (both disabled after validation).
