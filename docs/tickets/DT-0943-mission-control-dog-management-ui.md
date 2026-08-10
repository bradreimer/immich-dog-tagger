# Tickets

## **ID**

DT-0943

## **Related spec**

v0.9.4 Dynamic Dog Management

## **Priority**

High

## **Status**

Planned

## **Goal**

Add a Mission Control UI for managing dog identities.

## **Context**

Operators should be able to add and manage dogs from the web UI without editing files or the database directly.

## **Implementation notes**

* Add a dogs management surface to Mission Control.
* Show the current dog list and empty-state messaging.
* Support create/rename/remove actions through the API.
* Keep the UI usable on mobile and desktop.
* Preserve the existing review workflow while replacing the hard-coded identity chooser.

## **Acceptance criteria**

* Users can add a dog from the UI.
* Users can rename a dog from the UI.
* Users can remove or deactivate a dog from the UI.
* The UI shows an empty state when no dogs exist.
* The review flow consumes the dynamic dog list.
* Mobile layout remains usable.

## **Testing requirements**

* UI component tests or page tests.
* Empty-state test.
* CRUD interaction test.
* Mobile layout regression test.

## **Dependencies**

DT-0942

## **Suggested commit message**

`feat(ui): add mission control dog management`
