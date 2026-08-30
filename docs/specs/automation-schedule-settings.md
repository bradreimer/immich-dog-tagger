# Automation Schedule Settings

## Purpose

Automation Schedules currently lives on the Overview dashboard as a free-form list builder: a
name field, an operation dropdown, and a raw cron string, with schedules created and enabled one
at a time. This mixes long-lived configuration into a page meant for at-a-glance operational
status, and the free-form model lets users create redundant or oddly-named schedules for the same
operation. Move automation configuration to Settings, and replace the free-form builder with a
fixed set of pre-configured operations, each with just an enabled toggle and a cron expression, in
collapsible sections. This mirrors Immich's own Settings > Job Settings pattern (e.g. "Integrity
checks" containing "Missing files" and "Untracked files", each with an enable toggle and a cron
field with Crontab Guru guidance).

## User story

As an owner running Dog Tagger unattended,
I want to turn automatic scheduling on or off per operation and set its cadence from Settings,
so that I configure automation once, in the same place as my other preferences, without picking
through a list of ad hoc named schedules on the operational dashboard.

## Goals

- Remove the Automation Schedules card (creation form and schedule list) from
  `ui/src/features/overview/OverviewPage.tsx`.
- Add an "Automation" section to `ui/src/features/settings/SettingsPage.tsx` presenting one
  collapsible sub-section per pre-configured operation, each with:
  - An "Enable" toggle.
  - A cron expression field, with the same helper copy style as Immich's ("Set the scanning
    interval using the cron format. For more information please refer to e.g. Crontab Guru",
    linking out to crontab.guru).

Tracked as [#188](https://github.com/bradreimer/immich-dog-tagger/issues/188).
- Pre-configure exactly one schedule per supported operation (no user-chosen name, no operation
  picker) for: `full_pipeline` ("Process new photos"), `reclassify` ("Reclassify with reviewed
  examples"), `learn` ("Learn from reviewed examples"), and `sync` ("Publish labels back to
  Immich") — the same four whole-workflow operations already surfaced as Overview's manual-run
  actions plus `learn`. Raw pipeline stages (`scan`, `detect`, `embed`, `classify`) are not
  independently schedulable; `full_pipeline` already chains them.
- Preserve "Run Now" as a per-operation action within its section, since it remains useful for
  triggering an out-of-band run without waiting for the next scheduled occurrence.
- Preserve existing schedule status (next run, last run, last result) as read-only detail within
  each operation's section.
- Add the missing `Switch` and `Collapsible`/`Accordion` UI primitives this design needs (none
  currently exist under `ui/src/components/ui/`), consistent with the shadcn/ui-style primitives
  already used elsewhere.

## Non-goals

- Changing the underlying schedule data model (`PipelineSchedule`, `pipeline_schedules` table) or
  the scheduler/dispatcher execution logic in `src/immich_dog_tagger/services/schedules.py`. This
  is a UI relocation and simplification, not a scheduling-engine change.
- Supporting more than one schedule per operation, or arbitrary user-defined schedule names. If a
  future need for multiple schedules per operation emerges, it is a separate story.
- Timezone selection UI beyond what already exists (out of scope unless the existing default
  needs to move along with the rest of the form).
- Changing what "Run Now" does.
- A general-purpose Accordion/Collapsible or Switch component library beyond what this feature
  needs (build the minimal primitives required; don't design a generic system speculatively).

## Requirements

1. Overview (`OverviewPage.tsx`) no longer renders schedule creation or the schedule list. The
   `schedules`/`scheduleForm`/`scheduleBusy`/`scheduleMessage`/`scheduleError` state, the
   `handleCreateSchedule` and `toggleSchedule` handlers, and the `getSchedules`/`createSchedule`
   calls made from Overview are removed. Manual "Run" buttons (`operations` array, unrelated to
   scheduling) stay as-is.
2. Settings (`SettingsPage.tsx`) gains an "Automation" section, collapsed by default or expanded
   by default consistent with the other Settings sections' current convention, containing one
   collapsible entry per operation in Goals.
3. Each operation's collapsible entry shows, at minimum:
   - The operation's display name and a short description (reuse the copy already used for the
     manual-run buttons on Overview where an equivalent exists).
   - An enabled/disabled `Switch` bound to that operation's schedule `enabled` state.
   - A cron expression text field, pre-filled with the existing value or a sensible default (e.g.
     `0 * * * *`) if no schedule row exists yet for that operation.
   - Read-only next run / last run / last result detail once a schedule exists.
   - A "Run Now" button.
4. On first load, if a pre-configured operation has no corresponding `PipelineSchedule` row yet,
   the UI creates one lazily (via the existing `createSchedule` API) using a fixed, non-editable
   name derived from the operation (e.g. the operation's enum value) the first time the user
   enables it or edits its cron expression — or the backend/service seeds one row per known
   operation on startup, whichever keeps the "no delete/orphan schedule" invariant simplest.
   Whichever approach is chosen, a user must never be able to end up with zero, or more than one,
   schedule per pre-configured operation through this UI.
5. Editing the cron expression or toggling enabled calls the existing `updateSchedule` /
   `enableSchedule` / `disableSchedule` API functions in `ui/src/lib/api.ts`; no new backend
   endpoints are required for this story.
6. Cron expression validation errors from the existing backend validator
   (`PipelineScheduleService._validate_expression`) surface inline next to the field that produced
   them, not as a page-level toast only.
7. `docs/specs/v0.9.1-scheduling.md`, which currently states Mission Control (Overview) is "the
   place where schedules and automation are configured and observed," gets a short note pointing
   to this spec as superseding that statement for the UI location.

## Acceptance criteria

- Given the Overview page, when it loads, then no Automation Schedules card, schedule creation
  form, or schedule list is present.
- Given the Settings page, when it loads, then an "Automation" section is present with four
  collapsible sub-sections: Process new photos (`full_pipeline`), Reclassify with reviewed
  examples (`reclassify`), Learn from reviewed examples (`learn`), and Publish labels back to
  Immich (`sync`).
- Given a collapsed operation sub-section, when the user expands it, then it shows an enable
  toggle, a cron expression field with helper text, next/last run detail, and a Run Now button.
- Given an operation's enable toggle is off, when the user turns it on, then the corresponding
  schedule becomes enabled via the existing enable API and next-run information updates
  accordingly.
- Given a valid new cron expression is entered for an operation, when the field loses focus (or a
  save action is taken, per the chosen interaction pattern), then the schedule is updated via the
  existing update API and the new expression persists across a page reload.
- Given an invalid cron expression is entered, when it is submitted, then the field shows a
  validation error and the previous valid value remains in effect until corrected.
- Given "Run Now" is pressed for an operation, when a job is created, then the same confirmation
  behavior Overview provided today (a message including the created job id) is shown, without
  advancing the schedule's next-run time.
- Given a fresh install with no `pipeline_schedules` rows, when Settings' Automation section is
  first opened, then each of the four operations appears with a sensible default (disabled or a
  documented default state) rather than an empty/broken section.

## Out of scope

- Any change to which operations exist in `PipelineOperation` / `JobOperation`.
- Any change to the scheduler's due-occurrence evaluation, restart safety, or concurrency handling.
- A delete/archive endpoint for schedules (still not needed, since every pre-configured operation
  always has exactly one schedule row).
- Redesigning Settings sections unrelated to automation.

## Open questions

- Should `learn` be included as a fourth pre-configured, independently schedulable operation, or
  is it better run only as part of `full_pipeline`/on demand? It has no manual-run button on
  Overview today, unlike the other three. Decide during implementation; default assumption in
  this spec is to include it, since it was already schedulable via the old free-form dropdown and
  dropping it would be a capability regression.
- Seed-on-startup vs. lazy-create-on-first-edit for the one-row-per-operation invariant
  (Requirement 4) — pick whichever is less code, but must not silently create duplicate rows if
  both a startup seed and a lazy-create path exist.
- Default enabled/disabled state for pre-configured operations on a fresh install with no prior
  schedule rows — leaving all four disabled by default (matching "automation is opt-in") seems
  safest, but confirm during implementation.
