# Tickets

## **ID**

DT-0941

## **Related spec**

v0.9.4 Dynamic Dog Management

## **Priority**

High

## **Status**

Planned

## **Goal**

Make dog identities persistent data and ensure a clean installation starts with no preconfigured dogs.

## **Context**

Today the product still assumes a small fixed set of dogs in a few places. Before the UI can manage dogs dynamically, the underlying data model and startup behavior must clearly support an empty initial state.

## **Implementation notes**

* Audit the existing `Identity` and `EmbeddingExample` model usage.
* Define the persistence rules for operator-managed dogs.
* Ensure a fresh database starts with zero dog identities.
* Preserve existing review and learning references to identities.
* Add any migration or initialization cleanup required to remove seeded defaults.

## **Acceptance criteria**

* A clean database starts with no dogs configured.
* Dog identities persist in `state.db`.
* Existing review and learning records continue to resolve correctly.
* No hard-coded default dog seed remains.
* The empty state is documented and tested.

## **Testing requirements**

* Fresh-install database test.
* Identity persistence test.
* No-seed regression test.
* Review/learning compatibility test.

## **Dependencies**

v0.9.3 complete

## **Suggested commit message**

`feat(dogs): make dog identities persistent and empty by default`
