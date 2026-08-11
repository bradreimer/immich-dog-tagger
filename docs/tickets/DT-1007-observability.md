# TICKET 07: Logging and operational diagnostics

## Goal
Make failures diagnosable without exposing sensitive data.

## Steps
1. Add structured logs for pipeline/reclassification lifecycle.
2. Log counts, durations, identifiers, and stage names, not image contents or secrets.
3. Surface actionable errors in the UI.
4. Add enough context to distinguish stale jobs from active jobs.
5. Verify logs at normal and failure paths.

## Done when
A failed reclassification can be diagnosed from application logs and UI status without inspecting source code.
