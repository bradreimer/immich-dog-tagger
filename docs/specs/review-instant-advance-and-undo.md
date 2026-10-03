# Review: Instant Advance and Undo

Tracking issue: [#382](https://github.com/bradreimer/immich-dog-tagger/issues/382).

## Purpose

Choosing an identity in the review queue takes about 10 seconds before the next photo appears,
even with no pipeline job running. `ReviewPage.tsx`'s `correct()` waits for
`POST /classifications/{id}/correct` to finish, and that request runs OpenCLIP inference on the
crop (`ClassificationCorrectionService.correct()`) to store it as a learning example. Only then
does the page fetch fresh stats and show the next photo. The reviewer waits on work whose result
they don't need to see.

Advancing right away removes that wait, but it also removes the moment where a reviewer can
notice a slip before moving on. An undo action restores that safety net.

## User story

As a reviewer, I want the next photo to appear as soon as I choose an identity, and I want to
press `Z` to undo my last choice, so I can review quickly without worrying about a mistaken
keypress.

## Goals

- Choosing an identity (a specific dog or cat, or Unknown) in Queue mode shows the next photo
  immediately. The save continues in the background.
- `Z` (and an equivalent button) undoes the most recent identity choice: the photo comes back on
  screen, and the server state is restored to "not yet reviewed."
- Repeated `Z` presses undo earlier choices, newest first.
- Species correction keeps today's behavior: it waits for the rescore and stays on the same photo.
- The next photo's crop image is preloaded so it appears without a visible load.

## Non-goals

- Making the server-side correction itself faster (for example, reusing the stored crop
  embedding instead of re-running inference). That is separate work.
- Undo for Skip, Not a dog or cat, species correction, or Grouped mode batch approvals.
- Undo that survives a page reload. The undo history lives in the page only.

## Requirements

### Backend

- **FR-1** New endpoint `POST /classifications/{id}/undo-review` that reverses the latest
  identity correction for that classification.
- **FR-2** The latest `ReviewAction` for the classification must be `CORRECT`. Otherwise the
  endpoint returns 409 and changes nothing. A missing classification returns 404.
- **FR-3** Undo deletes that `ReviewAction` row, so the item counts as unreviewed again and
  returns to the active queue. It deletes only that one row. Older review history is untouched.
- **FR-4** Undo removes the learning example the correction created (`Learner.forget_image`)
  *before* rescoring, so the crop never matches its own example.
- **FR-5** Undo rescores the crop's stored embedding with `IdentityClassifier`, the same way
  species correction does, and sets `source` back to `AUTO`. The prediction is derived state, so
  it is recomputed rather than stored.
- **FR-6** Undo brings the crop's `PetOccurrence` in line with the restored prediction and queues
  the same debounced auto-reclassify that a correction does.
- **FR-7** The response is the restored item, in the same shape `GET /classifications/{id}`
  returns, so the UI can show it without another request.

### Frontend

- **FR-8** In Queue mode, choosing an identity removes the item from the queue at once and saves
  in the background. Stats refresh when the save finishes.
- **FR-9** If a background save fails, the item returns to the queue and an error is shown. A
  `404` (the item was reprocessed elsewhere) drops the item, as today.
- **FR-10** `Z` and an "Undo" button undo the most recent identity choice. If its save is still in
  flight, undo waits for it to finish first. The restored item is shown as the current photo.
- **FR-11** The Undo button is disabled when there is nothing to undo. Its label names the
  identity being undone.
- **FR-12** Reloading the queue (for example, changing the filter) drops any item whose save is
  still in flight, so it can't reappear and be reviewed twice.
- **FR-13** Species correction, Skip, and Not a dog or cat keep their current wait-then-update
  behavior.
- **FR-14** The next item's crop image is preloaded.
- **FR-15** Keyboard hints list `Z`.

## Acceptance criteria

- Pressing a number key shows the next photo without waiting for the server.
- Pressing `Z` right after shows the previous photo again, with its original prediction, and the
  item is back in the server's review queue with no `ReviewAction` and no learning example from
  that correction.
- Pressing `Z` twice undoes the two most recent choices, newest first.
- Changing species still stays on the same photo.
- Undoing a classification whose latest action isn't `CORRECT` returns 409.

## Open questions

- None.
