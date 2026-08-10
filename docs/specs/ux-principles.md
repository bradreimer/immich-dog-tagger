# UX Principles

**Status:** Active
**Scope:** Web UI
**Project:** Immich Dog Tagger

## Purpose

These principles define the user experience conventions for Immich Dog Tagger.

The goal is a UI that is **clear, fast, predictable, and unobtrusive**, particularly during repetitive photo-review workflows.

Contributors should use these principles when adding or changing UI components. When a specific component or feature has a documented design requirement, that requirement takes precedence.

## 1. Consistency Over Creativity

The interface should behave consistently across the application.

A user who learns how to perform an action in one part of the application should not have to learn a different interaction pattern elsewhere.

Prefer existing components, patterns, spacing, colors, and interaction behaviors over introducing new ones.

**Guideline:**

> If the application already has a way to do something, reuse it.

Avoid introducing one-off UI patterns unless there is a clear UX reason.

## 2. Actions Have a Consistent Visual Language

User actions should use a consistent visual treatment throughout the application.

Primary actions, secondary actions, destructive actions, and passive information should be visually distinguishable.

For example:

* **Primary:** prominent action that advances the workflow
* **Secondary:** useful but non-primary action
* **Destructive:** action that removes, rejects, or otherwise causes potentially irreversible change
* **Passive:** information that is not an action

The same action should look and behave the same way wherever it appears.

### Action buttons

Action buttons should use the application's established button components and styling.

Do not introduce arbitrary colors or button styles for individual features.

A contributor should not need to invent a new button color to communicate that an action is important.

Action buttons should use the shared orange action color language.

Hover behavior should be consistent across action buttons.

All action buttons should use the same hover interaction pattern (subtle elevation and background transition) so the UI gives a predictable signal that an action is clickable.

Non-action surfaces (cards, list rows, informational panels, and navigation labels) should not use mouse-over animation or hover-only visual effects.

Action buttons should include both text and an icon when practical.

For create-style actions, use an explicit `Create` text label with a plus icon from Tabler to make intent obvious.

## 3. Prefer Icons for Familiar Actions

Prefer a recognizable icon over text for simple, frequently used actions.

Examples include:

* Refresh
* Close
* Delete
* Edit
* Settings
* Previous / Next
* Expand / Collapse
* Confirm
* Reject
* Search
* Filter

Icons are particularly valuable in the review workflow because they reduce visual clutter and allow frequently repeated actions to be performed quickly.

### Icons must remain understandable

Do not replace text with an icon when the meaning would be ambiguous.

For unfamiliar, consequential, or destructive actions, use:

* An icon with a tooltip, or
* An icon together with text

For example, a trash icon can represent deletion, but an unfamiliar ML operation should not be represented by an arbitrary symbol simply to avoid text.

## 4. Use One Icon Library

The application should use a single primary icon library.

**Preferred library: Tabler Icons**

[Tabler Icons](https://tabler.io/icons?utm_source=chatgpt.com)

Tabler Icons should be preferred because it provides a large, consistent collection of freely available icons with a permissive license suitable for this project.

For the React application, use the official React package:

```text
@tabler/icons-react
```

Do not introduce additional icon libraries merely because a particular icon is missing.

If an appropriate Tabler icon does not exist, discuss the exception before adding another icon library.

## 5. Icon Buttons Need Accessible Names

An icon-only button must have an accessible name.

For example:

```tsx
<button aria-label="Refresh review queue">
    <IconRefresh />
</button>
```

Do not rely on the visual appearance of an icon as its only explanation.

Tooltips are useful for sighted users, but they do not replace an accessible name.

## 6. Optimize for the Review Workflow

The primary purpose of the UI is to help a human review and correct dog classifications efficiently.

The interface should therefore favor:

* Fast interactions
* Minimal navigation
* Clear visual hierarchy
* Keyboard-friendly workflows
* Obvious next actions
* Immediate feedback
* Minimal unnecessary confirmation dialogs
* Persistent context while reviewing

Avoid adding UI elements simply because they are technically possible.

Every control should earn its place.

## 7. Make State Obvious

The UI should clearly communicate what is happening.

Important states include:

* Loading
* Empty
* Ready
* Processing
* Success
* Error
* Reviewed
* Unreviewed
* Unknown
* Low confidence
* Selected
* Disabled

Do not make users infer application state from subtle visual changes.

For operations that may take significant time, show meaningful progress where practical.

## 8. Destructive Actions Should Be Deliberate

Actions that can delete data, discard work, or cause difficult-to-reverse changes should be visually distinct.

Use the established destructive-action styling rather than inventing a new treatment.

For potentially consequential operations:

* Make the action clear
* Explain what will happen when necessary
* Avoid accidental activation
* Provide confirmation when the consequence warrants it

Do not require confirmation for every action. Excessive confirmation dialogs make repetitive workflows unnecessarily slow.

## 9. Prefer Progressive Disclosure

Show the information required for the current task first.

Secondary information and advanced controls should be available without dominating the primary workflow.

For example, a review card might primarily show:

1. The detected dog
2. The current classification
3. The confidence/similarity
4. The available correction actions

Detailed metadata can be available through a secondary interaction.

The UI should not resemble an aircraft cockpit when the user is trying to identify a dog.

## 10. Use Clear, Specific Language

UI text should describe what an action actually does.

Prefer:

* `Confirm`
* `Reject`
* `Skip`
* `Retry`
* `Sync`
* `Refresh`
* `Delete`

over vague labels such as:

* `OK`
* `Do It`
* `Process`
* `Continue`

Where an action has a meaningful consequence, make that consequence apparent.

## 11. Feedback Should Be Immediate

When a user performs an action, the UI should provide immediate feedback.

Examples:

* A review action updates the current item
* A successful save is reflected in the UI
* A failed operation displays an error
* A background operation shows its current state

Avoid situations where the user clicks a button and cannot tell whether anything happened.

## 12. Keyboard Interaction Matters

The review workflow should be usable efficiently without requiring the mouse for every action.

Where appropriate:

* Provide keyboard shortcuts
* Make focus visible
* Preserve logical tab order
* Ensure interactive elements are keyboard accessible
* Avoid keyboard shortcuts that conflict with normal browser behavior

Keyboard shortcuts should complement the UI rather than being the only way to perform an action.

## 13. Accessibility Is Part of the UX

Accessibility is not a separate feature.

UI components should:

* Use semantic HTML where appropriate
* Provide accessible names
* Maintain sufficient contrast
* Show keyboard focus
* Avoid relying on color alone to communicate state
* Support keyboard interaction
* Provide meaningful feedback to assistive technologies where appropriate

An icon, color, or animation may reinforce meaning, but should not be the only way meaning is communicated.

## 14. Avoid Unnecessary Animation

Animation should communicate state or provide useful feedback.

Good uses include:

* Showing that something is loading
* Indicating a state transition
* Drawing attention to a newly changed item

Avoid decorative animation that slows down repetitive workflows or makes the interface distracting.

The review interface should feel fast even when processing large photo collections.

## 15. Responsive by Default

The application should remain usable across reasonable screen sizes.

Do not assume that every user has the same display dimensions as the developer.

When adding UI components:

* Avoid unnecessary fixed widths
* Allow content to reflow
* Keep important actions accessible
* Avoid horizontal scrolling where practical

Desktop is the primary environment, but the UI should not become unusable on smaller screens.

## 16. Errors Should Be Actionable

When something fails, tell the user:

1. What happened
2. What they can do about it

Prefer:

> Failed to sync 12 classifications. Retry the sync or inspect the error details.

over:

> Error: synchronization failed.

Technical details can be available for diagnosis without forcing every user to understand them.

## 17. Don't Hide Important Information

Important application state should not be hidden solely to make the UI look cleaner.

In particular, users should be able to understand:

* What is being processed
* What has been classified
* What needs review
* What failed
* What has been synchronized
* What action the application expects next

Minimalism should reduce noise, not reduce visibility.

## 18. Favor Reversible Actions

When choosing between two interaction designs, prefer the one that allows the user to recover from mistakes.

For example:

* Skip rather than delete
* Review later rather than discard
* Undo rather than requiring manual reconstruction

This is particularly important because the application operates on a user's personal photo library.

## 19. Don't Make the User Manage the Implementation

The UI should expose user concepts rather than implementation details.

Users care about:

* Dogs
* Photos
* Reviews
* Classifications
* Learning
* Synchronization

They generally do not care about:

* SQLAlchemy sessions
* Embedding vectors
* Internal service classes
* Database IDs
* Pipeline implementation details

Technical details may be exposed in diagnostics or advanced views when useful, but should not unnecessarily shape the primary workflow.

## 20. New Components Should Follow Existing Patterns

Before creating a new component, look for an existing component that already solves most of the problem.

When introducing a new reusable UI pattern:

1. Determine whether an existing component can be extended.
2. Follow existing spacing, typography, color, and interaction conventions.
3. Make the component reusable where appropriate.
4. Avoid creating a one-off visual language.

The UI should feel like one application, not a collection of contributions assembled at different times.

## 21. UX Decisions Should Favor the Human Reviewer

When principles conflict, prioritize the workflow of the person reviewing photos.

A useful hierarchy is:

1. **Correctness**
2. **Clarity**
3. **Speed**
4. **Consistency**
5. **Visual polish**

A beautiful interaction that causes classification mistakes is not a good interaction.

A slightly less elegant interaction that makes reviewing hundreds of photos substantially faster may be the better choice.

## 22. Adding a New UX Pattern

Before introducing a new interaction pattern, ask:

* Does an existing pattern already solve this?
* Is the action immediately understandable?
* Can the user recover from mistakes?
* Is the interaction keyboard accessible?
* Does it work without relying solely on color?
* Does it fit the review workflow?
* Does it add meaningful value?

If the answer to several of these is no, reconsider the design.

## Summary

Immich Dog Tagger's UI should be:

**Clear. Fast. Consistent. Accessible. Quiet.**

Prefer established patterns over invention, icons over unnecessary text, direct actions over unnecessary navigation, and useful information over decorative UI.

Most importantly, the interface should help a human teach the system about their dogs without making them fight the interface first.
