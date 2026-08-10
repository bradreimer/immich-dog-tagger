# Tickets

## **ID**

DT-0942

## **Related spec**

v0.9.4 Dynamic Dog Management

## **Priority**

High

## **Status**

Completed

## **Goal**

Expose dog identity management through the FastAPI backend.

## **Context**

The UI needs a supported API for listing and editing dog identities instead of hard-coding names in the browser.

## **Implementation notes**

* Add routes for list/create/update/delete dog identities.
* Keep validation and persistence in services.
* Reuse the existing `Identity` model where practical.
* Return useful API errors for duplicate or invalid names.
* Make deletion behavior explicit and safe.

## **Acceptance criteria**

* The API can list existing dogs.
* The API can create a new dog.
* The API can rename a dog.
* The API can remove or deactivate a dog according to the chosen lifecycle.
* Duplicate or invalid names are rejected.
* Existing review and learning APIs continue to work.

## **Testing requirements**

* API CRUD tests.
* Validation tests.
* Duplicate-name tests.
* Delete/deactivate regression tests.

## **Dependencies**

DT-0941

## **Suggested commit message**

`feat(api): expose dog management endpoints`

## **Validation results**

* API tests confirm a clean install returns no dogs.
* CRUD tests confirm create, rename, deactivate, and reactivate flows.
* Duplicate and reserved names are rejected with API errors.
* The dog listing can include or exclude inactive dogs.
