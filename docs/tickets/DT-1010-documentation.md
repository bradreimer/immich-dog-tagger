# DT-1010: v1.0 user and operator documentation

## **ID**

DT-1010

## **Related spec**

[v1.0.0 Product & Engineering Specification](../specs/v1.0.0.md) -- FR-10

## **Priority**

Medium

## **Status**

Pending

## **Goal**

Make the product understandable without ML expertise.

## **Context**

DT-1001 through DT-1009 deliver the review -> reclassify loop, its safety guarantees, and its metrics, but a new user still needs a written path from an empty project to progressively improved automatic classification -- what to do first, when to click Reclassify, and what the confidence states mean.

## **Steps**

1. Document first-project setup.
2. Explain the initial 50-100 review recommendation as a starting point, not a magic threshold.
3. Explain when to click Reclassify.
4. Explain confidence, needs-review, and unknown.
5. Explain the iterative workflow.
6. Document backups/state and recovery.
7. Document known v1.0 limitations, especially no temporal weighting and no separate training step.

## **Acceptance criteria**

A new user can follow the workflow from an empty project to progressively improved automatic classification using only the documentation.

## **Testing requirements**

Documentation-only ticket; reviewed for accuracy against the actual DT-1001-1009 implementation before merge.

## **Dependencies**

DT-1001 through DT-1009 (documents the finished feature set).

## **Suggested commit message**

`docs(DT-1010): add v1.0 user and operator documentation`
