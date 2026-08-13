# DT-1116: "Clear list" in Job Queue > History doesn't persist server-side

## **ID**

DT-1116

## **Related spec**

None -- bug fix, not new behavior. Reported as
[GitHub issue #12](https://github.com/bradreimer/immich-dog-tagger/issues/12).

## **Priority**

High

## **Status**

Completed

## **Goal**

Fix "Clear list" in Job Queue > History: clicking it should permanently hide those jobs from the
default job list, including after a browser refresh. Today it only clears the frontend's local
view -- refreshing brings the exact same job history right back, which the reporter (also the
project owner) called out directly: "The clear button is only clearing the view, not the job queue
on the server."

## **Context**

`JobQueuePage.tsx`'s `clearVisibleHistory()` added job IDs to a `hiddenHistoryIds` React
`useState<Set<number>>` and filtered them out of the `history` group client-side. Nothing was ever
sent to the server. On the next page load, `getJobs()` re-fetches the full, unfiltered list from
`GET /jobs`, `hiddenHistoryIds` resets to empty (it's local component state), and every job
reappears.

The issue's own suggested fix -- "tag jobs as `!visible` on the server, so that refreshing only
shows new jobs" -- is exactly right and is what this ticket implements: hide via a server-side
`visible` flag, not delete. `state.db` is the source of truth for job history (ADR-001); hidden
jobs must remain queryable/inspectable (e.g. `GET /jobs/{id}` still works), just excluded from the
default list.

## **Implementation notes**

- `models.py`: `PipelineJob` gains `visible: bool`, `nullable=False, default=True,
  server_default="1"`.
- `database.py`: `_ensure_pipeline_job_visible_column` -- plain `ALTER TABLE ... ADD COLUMN`
  (no uniqueness change, mirrors `_ensure_classification_pass_trend_columns`'s pattern). Every
  existing job migrates in as visible, which is correct: clearing is something an operator does
  going forward, not a retroactive change to what's currently displayed.
- `services/jobs.py`:
  - `PipelineJobRepository.list_recent()` now filters `WHERE visible = true` -- the one place
    `GET /jobs` reads from, so both the Job Queue page and Mission Control's job-derived stat tiles
    (which also call `getJobs()`) consistently stop showing cleared jobs.
  - New `PipelineJobRepository.hide_finished_jobs() -> int`: a bulk `UPDATE` setting
    `visible = false` for jobs whose status is `COMPLETED`/`FAILED`/`CANCELED` -- pending/running
    jobs are never touched, so an in-flight job can't be hidden out from under an operator watching
    it. Returns the row count.
  - New `PipelineJobService.clear_history() -> int`: calls the repository method and commits.
- `api/routes/jobs.py`: new `POST /jobs/clear-history`, returning `{"cleared": <count>}` (no
  `response_model`, matching `review.py`'s `skip_review`'s plain-dict-response precedent).
- `JobQueuePage.tsx`: removed `hiddenHistoryIds` entirely; `clearVisibleHistory` now calls the new
  `clearJobHistory()` API function and reloads the job list from the server, so the button's effect
  and a page refresh's effect are identical -- there's no longer a separate client-only state to
  drift from server state.
- No confirmation dialog added -- consistent with this codebase's existing "minimal confirmation
  for non-destructive actions" stance (per `ux-principles.md`) and the fact that clearing hides
  rows, it doesn't delete them.

## **Acceptance criteria**

- Clicking "Clear list", then refreshing the browser, leaves the History section empty (previously
  the full list reappeared) -- reproduced and verified live against a running API instance with the
  exact repro from the issue (create a job, cancel it into history, `GET /jobs`, `POST
  /jobs/clear-history`, `GET /jobs` again) before and after the fix.
- A cleared job is hidden from `GET /jobs`, not deleted -- `GET /jobs/{id}` still returns it.
- Pending and running jobs are never hidden by `clear-history`, even if called while jobs are
  in-flight.
- Existing databases migrate in with every job visible; no jobs are retroactively hidden.

## **Testing requirements**

- `tests/test_jobs.py`: `hide_finished_jobs()`/`clear_history()` hide only terminal-status jobs and
  leave pending/running ones visible; calling `clear_history()` twice in a row is idempotent
  (second call clears 0).
- `tests/api/test_jobs.py`: `POST /jobs/clear-history` removes cleared jobs from a subsequent
  `GET /jobs`, while `GET /jobs/{id}` still resolves them directly.
- `tests/test_database.py`: migration test for the new `visible` column on a pre-DT-1116
  `pipeline_jobs` table, following the existing `_ensure_*_column` test pattern.
- Full `./scripts/check.sh` passes.

## **Dependencies**

None.

## **Suggested commit message**

`fix(DT-1116): persist "Clear list" server-side so History stays cleared after a refresh`
